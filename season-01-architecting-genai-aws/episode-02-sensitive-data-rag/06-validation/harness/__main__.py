"""Command-line entry point: python3 -m harness <command> (run from 06-validation/)."""
import argparse
import json
import os
import shutil
import sys
import time
from datetime import datetime, timezone

from harness import calibration, fixtures, results, runbook, suites
from harness.common import RESULTS, redact
from harness.context import Context
from harness.identities import Identities
from harness.target import Target


def _run_id(prefix):
    return f"{prefix}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"


def cmd_fixtures(args):
    target = Target(args.variant)
    print(json.dumps(fixtures.load(target, Identities(target)), indent=2))
    return 0


def cmd_ask(args):
    target = Target(args.variant)
    ctx = Context(target, None)
    observation = ctx.ask(args.as_persona, args.question)
    print(json.dumps(redact(observation.view()), indent=2, default=str))
    print(f"ineligible canaries seen: {ctx.leaks(observation)}")
    return 0


def cmd_inventory(args):
    target = Target(args.variant)
    ctx = Context(target, None)
    inventory = ctx.obs.inventory()
    for tier, content in inventory.items():
        print(f"{tier}: {len(content['chunks'])} chunks, {len(content['section_objects'])} section objects")
        for chunk in sorted(content["chunks"], key=lambda c: (c["document_id"] or "", c["section_id"] or "")):
            print(f"   {chunk['document_id']}-{chunk['section_id']} {chunk['label']}/{chunk['scope']} v{chunk['record_version']} {chunk['canaries']}")
    return 0


def cmd_run(args):
    target = Target(args.variant)
    tests = suites.ORDER if args.tests == "all" else args.tests.split(",")
    unknown = [t for t in tests if t not in suites.ORDER]
    if unknown:
        print(f"unknown or runbook-only tests: {unknown}")
        return 2
    run = results.Run(args.run_id or _run_id(f"{args.variant}-run"), target, f"tests {args.tests}")
    ctx = Context(target, run)
    if "TST-SEC-001" in tests:
        ctx.expiry_probe = {"token": ctx.ids.token(ctx.username("P-01"), fresh=True), "issued_at": time.time()}
    suites.run_tests(ctx, tests)
    return run.finish()


def cmd_calibrate(args):
    target = Target("normal")
    run = results.Run(args.run_id or _run_id("relevance-calibration"), target, "relevance calibration")
    document = calibration.calibrate(target)
    run.attach("relevance-calibration.json", document)
    print(json.dumps({"summary": document["summary"], "selected_threshold": document["selected_threshold"],
                      "reason": document["reason"], "independence": {k: v for k, v in document["independence"].items()
                                                                     if not k.endswith("privileged") and k != "constrained_search"}},
                     indent=2))
    run.finish()
    return 0


def cmd_measure_filter_limit(args):
    from harness import platform
    target = Target("normal")
    run = results.Run(args.run_id or _run_id("filter-limit"), target, "platform filter-size re-measurement")
    document = platform.measure(target)
    run.attach("filter-size-measurement.json", document)
    print(json.dumps({"boundaries": {p: {k: {x: v.get(x) for x in ("grants", "default_bytes", "compact_bytes", "accepted",
                                                                     "layer", "message")} for k, v in b.items()
                                         if isinstance(v, dict)} for p, b in document["boundaries"].items()},
                      "all_accepted_honoured_last_grant": document["all_accepted_honoured_last_grant"],
                      "distinct_rejections": document["distinct_rejections"]}, indent=2))
    run.finish()
    return 0


def cmd_export_audit(args):
    from harness import usage
    print(json.dumps(usage.export_audit(Target(args.variant), args.run_id), indent=2))
    return 0


def cmd_update_traceability(args):
    from harness import traceability
    summary = traceability.update(args.evidence_root, args.run_id, args.state or ["**State:** results from executed runs."])
    print(json.dumps({k: v for k, v in summary.items() if k != "statuses"}, indent=2))
    print(json.dumps(summary["statuses"], indent=2))
    return 0


def cmd_experiment(args):
    return runbook.experiment(args.number, args.label)


def cmd_verify_cleanup(args):
    from harness.common import tla_ops
    variants = list(tla_ops.VARIANTS) if args.variant == "all" else [args.variant]
    return runbook.verify_cleanup_run(args.run_id or _run_id(f"cleanup-{args.variant}"), variants)


def cmd_full_run(args):
    return runbook.full_run(args.label, args.reference_run)


def cmd_evidence(args):
    os.makedirs(args.out, exist_ok=True)
    for run_id in args.run_id:
        destination = os.path.join(args.out, run_id)
        shutil.rmtree(destination, ignore_errors=True)
        shutil.copytree(os.path.join(RESULTS, run_id), destination)
        for directory, _, files in os.walk(destination):           # redact again: covers runs written earlier
            for name in files:
                if name.endswith((".json", ".jsonl", ".md")):
                    path = os.path.join(directory, name)
                    with open(path, encoding="utf-8") as handle:
                        text = handle.read()
                    with open(path, "w", encoding="utf-8") as handle:
                        handle.write(redact(text))
        print(f"bundled {run_id} → {destination}")
    return 0


def main():
    parser = argparse.ArgumentParser(prog="python3 -m harness")
    sub = parser.add_subparsers(dest="command", required=True)
    variants = ["normal", "eligibility-removed", "labels-corrupted", "claims-as-grants"]
    p = sub.add_parser("fixtures"); p.add_argument("action", choices=["load"]); p.add_argument("--variant", default="normal", choices=variants)
    p.set_defaults(func=cmd_fixtures)
    p = sub.add_parser("ask"); p.add_argument("question"); p.add_argument("--as", dest="as_persona", required=True)
    p.add_argument("--variant", default="normal", choices=variants); p.set_defaults(func=cmd_ask)
    p = sub.add_parser("inventory"); p.add_argument("--variant", default="normal", choices=variants); p.set_defaults(func=cmd_inventory)
    p = sub.add_parser("run"); p.add_argument("--tests", default="all"); p.add_argument("--variant", default="normal", choices=variants)
    p.add_argument("--run-id"); p.set_defaults(func=cmd_run)
    p = sub.add_parser("calibrate-relevance"); p.add_argument("--run-id"); p.set_defaults(func=cmd_calibrate)
    p = sub.add_parser("measure-filter-limit"); p.add_argument("--run-id"); p.set_defaults(func=cmd_measure_filter_limit)
    p = sub.add_parser("export-audit"); p.add_argument("--run-id", required=True)
    p.add_argument("--variant", default="normal", choices=variants); p.set_defaults(func=cmd_export_audit)
    p = sub.add_parser("update-traceability"); p.add_argument("--evidence-root", required=True)
    p.add_argument("--run-id", action="append", required=True); p.add_argument("--state", action="append", default=[])
    p.set_defaults(func=cmd_update_traceability)
    p = sub.add_parser("experiment"); p.add_argument("number", type=int, choices=[1, 2, 3]); p.add_argument("--label")
    p.set_defaults(func=cmd_experiment)
    p = sub.add_parser("verify-cleanup"); p.add_argument("--variant", default="all", choices=["all"] + variants)
    p.add_argument("--run-id"); p.set_defaults(func=cmd_verify_cleanup)
    p = sub.add_parser("full-run"); p.add_argument("--label", required=True); p.add_argument("--reference-run")
    p.set_defaults(func=cmd_full_run)
    p = sub.add_parser("evidence"); p.add_argument("action", choices=["bundle"]); p.add_argument("--run-id", action="append", required=True)
    p.add_argument("--out", required=True); p.set_defaults(func=cmd_evidence)
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
