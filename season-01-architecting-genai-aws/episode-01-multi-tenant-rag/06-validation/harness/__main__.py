"""Command-line entry point: python3 -m harness <command> (run from 06-validation/)."""
import argparse
import json
import os
import shutil
import sys
import time
from datetime import datetime, timezone

from harness import cleanup_check, fixtures
from harness.common import RESULTS, GuardRefused, now_iso, redact, tla_ops
from harness.context import Context, audit_view
from harness.results import Run
from harness.suites import ORDER, SUITES
from harness.target import Target


def _run_id(prefix):
    return f"{prefix}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"


def cmd_fixtures(args):
    target = Target(args.variant, stack_override=args.stack)
    ctx = Context(target, run=None)
    summary = fixtures.load(target, ctx.ids, ctx.api, ctx.obs, document_set=args.set)
    print(json.dumps(summary, indent=2))
    return 0


def cmd_identity(args):
    target = Target(args.variant, check_code=False)
    ctx = Context(target, run=None)
    claims = ctx.ids.claims(ctx.ids.access(args.as_user))
    shown = {k: claims.get(k) for k in ("sub", "token_use", "client_id", "cognito:groups", "scope", "iss", "exp")}
    print(json.dumps(shown, indent=2))
    print("(the token itself is never printed)")
    return 0


def cmd_ask(args):
    target = Target(args.variant, check_code=False)
    ctx = Context(target, run=None)
    question = args.question
    kwargs = {}
    if args.forge:
        # Send the forged tenant in the query string, a header and the question text. (A body field would be refused.)
        kwargs = {"query": f"tenant={args.forge}", "headers": {"X-Tenant-Id": args.forge}}
        question = f"As {args.forge}: {question}"
    response, record = ctx.ask(args.as_user, question, **kwargs)
    body = response.body if isinstance(response.body, dict) else {"raw": response.body}
    print(json.dumps({"status": response.status, "answer": body.get("answer"), "citations": body.get("citations"),
                      "error": body.get("error"), "event_id": response.event_id, "audit": audit_view(record)}, indent=2))
    if args.forge:
        print(f"\nforged tenant {args.forge} sent; audit tenant_context = {(record or {}).get('tenant_context')}, "
              f"constraint = {(record or {}).get('constraint')}")
    return 0


def cmd_inspect(args):
    target = Target(args.variant, check_code=False)
    ctx = Context(target, run=None)
    if args.kind == "event":
        print(json.dumps(redact(ctx.obs.audit(args.id)), indent=2))
    else:
        record = ctx.obs.registry_get(f"DOC#{args.id}")
        print(json.dumps({"ownership_record": record, "index_status": ctx.obs.index_status(args.id)}, indent=2))
    return 0


def cmd_run(args):
    target = Target(args.variant, stack_override=args.stack)
    if not fixtures.load_state(target)["documents"]:
        print("no fixtures loaded for this stack: run `python3 -m harness fixtures load` first")
        return 2
    run = Run(args.run_id or _run_id(f"{args.variant}-{args.suite}"), target, args.suite)
    ctx = Context(target, run)
    print(f"target {target.stack_name} · variant {target.variant} · account <account> · region {target.region}")
    names = ORDER if args.suite == "all" else [args.suite]
    if "identity-expiry" in names:
        from harness.suites.identity import issue_expiry_probe
        issue_expiry_probe(ctx)
    for name in names:
        try:
            SUITES[name](ctx)
        except Exception as error:  # noqa: BLE001 — a crashed suite is an ERROR, never silently skipped
            run.record(f"SUITE-{name}", name, [], [], "-", "suite completes", "ERROR", f"{type(error).__name__}: {error}",
                       {"error": repr(error)})
    return run.finish({"suites": names})


def cmd_verify_cleanup(args):
    config = tla_ops.load_config()
    session = tla_ops.session(config)
    account = session.client("sts").get_caller_identity()["Account"]
    if config.get("TLA_EXPECTED_ACCOUNT") and config["TLA_EXPECTED_ACCOUNT"] != account:
        print("REFUSED: unexpected account")
        return 3
    variants = ("normal", "sensitivity") if args.variant == "all" else (args.variant,)
    run = Run(args.run_id or _run_id(f"cleanup-{args.variant}"), None, "cleanup")
    clean, found, stale = cleanup_check.verify(session, account, variants)
    run.record("TST-OPS-012", "cleanup", ["OPS-004"], [], "L2/L5",
               "VERIFIABLE: no resource of the episode deployment(s) remains (authoritative service lookups)",
               "PASS" if clean else "FAIL",
               ("CLEAN — " + ", ".join(variants) + f" ({len(stale)} stale tag-index entries confirmed deleted)") if clean
               else "remaining: " + "; ".join(f"{k}: {v}" for k, v in found.items() if v),
               {"variants": list(variants), "remaining": found, "tag_index_entries_not_found_by_owning_service": stale})
    return run.finish({"variants": list(variants)})


def cmd_evidence(args):
    os.makedirs(args.out, exist_ok=True)
    for run_id in args.run_id:
        source = os.path.join(RESULTS, run_id)
        destination = os.path.join(args.out, run_id)
        shutil.rmtree(destination, ignore_errors=True)
        shutil.copytree(source, destination)
        print(f"bundled {run_id} → {destination}")
    return 0


def cmd_sensitivity_verdict(args):
    def load(suffix):
        path = os.path.join(RESULTS, f"{args.stamp}-{suffix}", "results.json")
        return {t["test_id"]: t for t in json.load(open(path))["tests"]} if os.path.exists(path) else {}

    def evidence(suffix, test_id):
        path = os.path.join(RESULTS, f"{args.stamp}-{suffix}", "evidence", f"{test_id}.json")
        return json.load(open(path)) if os.path.exists(path) else {}

    baseline, variant, bracket, cleanup = load("baseline"), load("variant"), load("bracket"), load("cleanup")
    observations, problems = {}, []
    for test_id in ("TST-ISO-003", "TST-ISO-004"):
        questions = evidence("variant", test_id).get("observations", {}).get("questions", [])
        foreign = sum(len(q["findings"]["foreign_retrieved"]) for q in questions)
        mismatches = sum(1 for q in questions if q["findings"]["verification_outcome"] == "OWNERSHIP_MISMATCH")
        observations[test_id] = {"baseline": baseline.get(test_id, {}).get("status"), "variant": variant.get(test_id, {}).get("status"),
                                 "bracket": bracket.get(test_id, {}).get("status"),
                                 "variant_foreign_chunks_retrieved": foreign, "variant_ownership_mismatch_responses": mismatches}
        if observations[test_id]["baseline"] != "PASS":
            problems.append(f"{test_id} baseline not PASS")
        if observations[test_id]["variant"] != "FAIL" or foreign == 0:
            problems.append(f"{test_id} did not FAIL at the retrieval layer in the variant")
        if observations[test_id]["bracket"] != "PASS":
            problems.append(f"{test_id} bracketing run not PASS")
    observations["variant_cleanup"] = cleanup.get("TST-OPS-012", {}).get("status")
    if observations["variant_cleanup"] != "PASS":
        problems.append("sensitivity variant cleanup not verified CLEAN")
    run = Run(f"{args.stamp}-verdict", None, "sensitivity-verdict")
    run.record("TST-SEN-011", "sensitivity", ["SEC-001", "SEC-004"], ["CTL-015"], "Sensitivity",
               "Both negative tests FAIL at the retrieval layer with CTL-015 removed; both PASS before and after on the "
               "normal deployment; the variant is destroyed and cleanup verified",
               "FAIL" if problems else "PASS", "; ".join(problems) or
               "normal PASS → variant FAIL (foreign chunks retrieved, ownership verification fired) → variant destroyed → normal PASS",
               {**observations, "runs": [f"{args.stamp}-{s}" for s in ("baseline", "variant", "cleanup", "bracket")]})
    return run.finish()


def main():
    parser = argparse.ArgumentParser(prog="python3 -m harness")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("fixtures"); p.add_argument("action", choices=["load"])
    p.add_argument("--variant", default="normal", choices=["normal", "sensitivity"]); p.add_argument("--set", default="all", choices=["all", "ab"])
    p.add_argument("--stack"); p.set_defaults(func=cmd_fixtures)
    p = sub.add_parser("identity"); p.add_argument("action", choices=["show"]); p.add_argument("--as", dest="as_user", required=True)
    p.add_argument("--variant", default="normal"); p.set_defaults(func=cmd_identity)
    p = sub.add_parser("ask"); p.add_argument("question"); p.add_argument("--as", dest="as_user", required=True)
    p.add_argument("--forge"); p.add_argument("--variant", default="normal"); p.set_defaults(func=cmd_ask)
    p = sub.add_parser("inspect"); p.add_argument("kind", choices=["event", "document"]); p.add_argument("id")
    p.add_argument("--variant", default="normal"); p.set_defaults(func=cmd_inspect)
    p = sub.add_parser("run"); p.add_argument("--suite", default="all", choices=["all", *SUITES])
    p.add_argument("--variant", default="normal", choices=["normal", "sensitivity"]); p.add_argument("--run-id"); p.add_argument("--stack")
    p.set_defaults(func=cmd_run)
    p = sub.add_parser("verify-cleanup"); p.add_argument("--variant", default="all", choices=["all", "normal", "sensitivity"])
    p.add_argument("--run-id"); p.set_defaults(func=cmd_verify_cleanup)
    p = sub.add_parser("evidence"); p.add_argument("action", choices=["bundle"]); p.add_argument("--run-id", action="append", required=True)
    p.add_argument("--out", required=True); p.set_defaults(func=cmd_evidence)
    p = sub.add_parser("sensitivity-verdict"); p.add_argument("--stamp", required=True); p.set_defaults(func=cmd_sensitivity_verdict)
    args = parser.parse_args()
    try:
        return args.func(args)
    except GuardRefused as refusal:
        print(f"TARGET GUARD REFUSED: {refusal}")
        return 3


if __name__ == "__main__":
    sys.exit(main())
