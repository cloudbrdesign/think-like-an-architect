"""Runbook: the three failure experiments (TST-SEN-001 … 003) and the fresh-copy run (TST-OPS-001).

Every experiment:  baseline on normal (PASS) → build + deploy its variant (own stack) → load fixtures → target tests on
the variant (expected FAIL, for the predicted reason) → destroy the variant and verify → restored run on normal (PASS)
→ verdict. The variant is destroyed in a `finally`, even after an error.
"""
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone

from harness import canaries, cleanup_check, fixtures, results, suites, usage
from harness.common import IMPLEMENTATION, RESULTS, VALIDATION, now_iso, tla_ops
from harness.context import Context
from harness.identities import Identities
from harness.target import Target

EXPERIMENTS = {
    1: {"variant": "eligibility-removed", "test": "TST-SEN-001", "verifies": ["SEC-001", "SEC-004"],
        "controls": ["CTL-011", "CTL-012", "CTL-014"],
        "fault": "mandatory retrieval eligibility constraint removed (label-only constraint, both tiers for everyone)"},
    2: {"variant": "labels-corrupted", "test": "TST-SEN-002", "verifies": ["SEC-008", "DATA-003"],
        "controls": ["CTL-008", "CTL-014"],
        "fault": "label propagation corrupted (every section inherits its document label and is routed by it)"},
    3: {"variant": "claims-as-grants", "test": "TST-SEN-003", "verifies": ["SEC-010"], "controls": ["CTL-003"],
        "fault": "stale token group claims used as current domain and case grants"},
}


def stamp():
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def ops(*arguments, sensitivity=False):
    env = dict(os.environ, **({"TLA_SENSITIVITY_RUN": "1"} if sensitivity else {}))
    started = time.time()
    process = subprocess.run([sys.executable, "-B", os.path.join(IMPLEMENTATION, "scripts", "tla_ops.py"), *arguments],
                             cwd=IMPLEMENTATION, env=env, capture_output=True, text=True)
    output = (process.stdout + process.stderr).strip().splitlines()
    for line in output[-8:]:
        print(f"    {line}")
    return {"command": " ".join(arguments), "exit": process.returncode, "seconds": int(time.time() - started),
            "output_tail": output[-8:]}


def harness(*arguments):
    """Run one harness step in its own short-lived process (bounded memory per step on small machines)."""
    started = time.time()
    process = subprocess.run([sys.executable, "-B", "-u", "-m", "harness", *arguments], cwd=VALIDATION)
    return {"command": " ".join(arguments), "exit": process.returncode, "seconds": int(time.time() - started)}


def run_tests(variant, test_ids, run_id, with_expiry_probe=False):
    target = Target(variant)
    run = results.Run(run_id, target, f"tests {','.join(test_ids)}")
    ctx = Context(target, run)
    if with_expiry_probe:
        ctx.expiry_probe = {"token": ctx.ids.token(ctx.username("P-01"), fresh=True), "issued_at": time.time()}
    suites.run_tests(ctx, test_ids)
    run.finish()
    return results.load(run_id)


def statuses(document):
    return {t["test_id"]: t["status"] for t in document["tests"]}


def _views(value):
    if isinstance(value, dict):
        if "persona" in value and "retrieved" in value and "outcome" in value:
            yield value
        for child in value.values():
            yield from _views(child)
    elif isinstance(value, list):
        for child in value:
            yield from _views(child)


def evidence(run_id, test_id):
    with open(os.path.join(RESULTS, run_id, "evidence", f"{test_id}.json"), encoding="utf-8") as handle:
        return json.load(handle)


def retrieval_layer_findings(run_id, test_ids):
    """Every ask in the variant run whose RETRIEVAL list held a section the persona is not eligible for (oracle), and
    what happened next: verification outcome and whether the model was invoked."""
    oracle, findings = canaries.oracle(), []
    for test_id in test_ids:
        seen = set()
        for view in _views(evidence(run_id, test_id)):
            if view["request_id"] in seen:
                continue
            seen.add(view["request_id"])
            leaked = sorted({f"{r['document_id']}-{r['section_id']}" for r in view["retrieved"]
                             if view["persona"] not in oracle.get(f"{r['document_id']}-{r['section_id']}", {}).get("eligible", [])})
            if leaked:
                findings.append({"test": test_id, "persona": view["persona"], "question": view["question"],
                                 "ineligible_sections_retrieved": leaked, "outcome": view["outcome"],
                                 "generation_invoked": view["generation_invoked"],
                                 "contained_before_generation": view["outcome"] == "WITHHELD_VERIFICATION_MISMATCH"
                                 and not view["generation_invoked"]})
    return findings


def experiment(number, label=None):
    spec = EXPERIMENTS[number]
    variant, targets = spec["variant"], suites.EXPERIMENT_TARGETS[number]
    base = f"sen{number}-{label or stamp()}"
    print(f"== experiment {number}: {spec['fault']}")
    print("== 1 baseline on the normal deployment")
    baseline = run_tests("normal", targets, f"{base}-baseline")
    steps, variant_doc, cleanup = [], None, None
    try:
        print(f"== 2 fault introduced: build and deploy variant {variant}")
        steps.append(ops("build", variant))
        steps.append(ops("deploy", variant, sensitivity=True))
        if steps[-1]["exit"] != 0 or steps[-2]["exit"] != 0:
            raise RuntimeError(f"variant deployment failed: {steps[-2:]}")
        target = Target(variant)
        steps.append({"command": "fixtures load", "summary": fixtures.load(target, Identities(target))})
        print("== 3 target tests against the variant (expected to FAIL)")
        variant_doc = run_tests(variant, targets, f"{base}-variant")
        steps.append({"command": "export variant audit", "usage": usage.export_audit(target, f"{base}-variant")})
    finally:
        print("== 4 fault removed: destroy the variant and verify")
        session_target = tla_ops.session(tla_ops.load_config())
        account = tla_ops.account_guard(tla_ops.load_config(), session_target, quiet=True)
        failed, lines = tla_ops.cleanup(session_target, account, [variant])
        clean, found, stale = cleanup_check.verify(session_target, account, [variant])
        cleanup = {"cleanup_failed": failed, "lines": lines, "verified_clean": clean, "remaining": found,
                   "tag_index_entries_not_found_by_owning_service": stale}
        run = results.Run(f"{base}-cleanup", None, f"cleanup {variant}")
        run.record("CLEANUP", "cleanup", ["OPS-003"], [], "L2", f"no resource of the {variant} deployment remains",
                   "PASS" if clean and not failed else "FAIL",
                   "CLEAN" if clean else f"remaining {found}", cleanup)
        run.finish()
    print("== 5 restored run on the normal deployment")
    restored = run_tests("normal", targets, f"{base}-restored")
    return verdict(number, base, baseline, variant_doc, cleanup, restored, steps)


def verdict(number, base, baseline, variant_doc, cleanup, restored, steps):
    spec = EXPERIMENTS[number]
    targets = suites.EXPERIMENT_TARGETS[number]
    problems, observations = [], {"fault": spec["fault"], "variant": spec["variant"], "steps": steps,
                                  "runs": {s: f"{base}-{s}" for s in ("baseline", "variant", "cleanup", "restored")}}
    observations["baseline"], observations["restored"] = statuses(baseline), statuses(restored)
    observations["variant_statuses"] = statuses(variant_doc) if variant_doc else None
    if any(s != "PASS" for s in observations["baseline"].values()):
        problems.append("baseline not all PASS")
    if not variant_doc or any(observations["variant_statuses"].get(t) != "FAIL" for t in targets):
        problems.append(f"variant target tests did not all FAIL: {observations['variant_statuses']}")
    if variant_doc:
        findings = retrieval_layer_findings(f"{base}-variant", targets)
        observations["retrieval_layer_findings"] = findings
        if number == 1:
            observations["security_boundary"] = "FAILED AT RETRIEVAL" if findings else "no retrieval-layer failure observed"
            observations["secondary_verification"] = ("DETECTED AND CONTAINED every leaked request before generation"
                                                      if findings and all(f["contained_before_generation"] for f in findings)
                                                      else "did NOT contain every leaked request")
            if not findings:
                problems.append("no ineligible section crossed the retrieval boundary: the tests would be blind")
            if not all(f["contained_before_generation"] for f in findings):
                problems.append("verification did not withhold every leaked request")
        if number == 2:
            p01 = [f for f in findings if f["persona"] == "P-01" and "D-03-S4" in f["ineligible_sections_retrieved"]]
            observations["corrupted_metadata_changed_retrieval"] = bool(p01)
            observations["secondary_verification"] = ("DETECTED the authoritative classification mismatch and withheld"
                                                       if p01 and all(f["contained_before_generation"] for f in p01)
                                                       else "did NOT withhold")
            if not p01:
                problems.append("corrupted label did not change retrieval eligibility for P-01")
        if number == 3:
            after = evidence(f"{base}-variant", "TST-CHG-001")["observations"]["after"]
            bid = [r for r in after["retrieved"] if r["document_id"] in ("D-03", "D-14")]
            observations["after_revocation_same_token"] = {"retrieved_bid_orion": [f"{r['document_id']}-{r['section_id']}" for r in bid],
                                                           "decision": after["decision"], "outcome": after["outcome"],
                                                           "generation_invoked": after["generation_invoked"]}
            observations["secondary_verification"] = (
                "did not contain it: verification checks chunks against the request's decision, and the decision itself "
                "was built from stale claims" if after["outcome"] == "ANSWERED" else f"outcome {after['outcome']}")
            if not bid:
                problems.append("the stale token did not retrieve BID-ORION after revocation")
    if not cleanup or not cleanup["verified_clean"] or cleanup["cleanup_failed"]:
        problems.append("variant cleanup not verified")
    if any(s != "PASS" for s in observations["restored"].values()):
        problems.append("restored run not all PASS")
    run = results.Run(f"{base}-verdict", None, f"experiment {number}")
    run.record(spec["test"], "sensitivity", spec["verifies"], spec["controls"], "L4",
               "Baseline PASS → variant target tests FAIL for the predicted reason → variant destroyed and verified → "
               "restored PASS", "FAIL" if problems else "PASS",
               "; ".join(problems) or f"baseline PASS → variant FAIL ({observations.get('secondary_verification')}) → "
               "variant destroyed, cleanup verified → restored PASS", observations)
    return run.finish()


def full_run(label, reference_run=None):
    """TST-OPS-001: preflight → build → deploy → fixtures → all tests → three experiments → cleanup → verify."""
    log, run_ids = [], {}

    def step(name, function):
        started = now_iso()
        try:
            outcome = function()
            code = outcome if isinstance(outcome, int) else (outcome or {}).get("exit", 0)
        except Exception as error:  # noqa: BLE001
            code, outcome = 99, f"{type(error).__name__}: {error}"
        log.append({"step": name, "started": started, "finished": now_iso(), "exit": code,
                    "detail": outcome if not isinstance(outcome, int) else None})
        print(f"[{name}] exit {code}")
        return code

    try:
        if step("preflight", lambda: ops("preflight")) != 0:
            return _record_full_run(label, log, run_ids, reference_run, aborted="preflight failed")
        step("build normal", lambda: ops("build", "normal"))
        if step("deploy normal", lambda: ops("deploy", "normal")) != 0:
            return _record_full_run(label, log, run_ids, reference_run, aborted="deploy failed")
        step("fixtures load", lambda: harness("fixtures", "load"))
        run_ids["all"] = f"{label}-normal-all"
        step("validation suite", lambda: harness("run", "--tests", "all", "--run-id", run_ids["all"]))
        for number in (1, 2, 3):
            run_ids[f"experiment-{number}"] = f"sen{number}-{label}"
            step(f"experiment {number}", lambda n=number: harness("experiment", str(n), "--label", label))
    finally:
        step("export normal audit", lambda: harness("export-audit", "--run-id", f"{label}-normal-all"))
        step("cleanup all", lambda: _cleanup_all())
        run_ids["cleanup"] = f"{label}-cleanup-all"
        step("verify cleanup", lambda: verify_cleanup_run(run_ids["cleanup"], list(tla_ops.VARIANTS)))
    return _record_full_run(label, log, run_ids, reference_run)


def _cleanup_all():
    config = tla_ops.load_config()
    session = tla_ops.session(config)
    failed, lines = tla_ops.cleanup(session, tla_ops.account_guard(config, session, quiet=True), list(tla_ops.VARIANTS))
    return {"exit": int(failed), "lines": lines}


def verify_cleanup_run(run_id, variants):
    config = tla_ops.load_config()
    session = tla_ops.session(config)
    account = tla_ops.account_guard(config, session, quiet=True)
    clean, found, stale = cleanup_check.verify(session, account, variants)
    run = results.Run(run_id, None, "cleanup")
    run.record("CLEANUP", "cleanup", ["OPS-003"], [], "L2/L5",
               "no resource of the Episode 02 deployments remains (authoritative service lookups)",
               "PASS" if clean else "FAIL", "CLEAN — " + ", ".join(variants) if clean else f"remaining {found}",
               {"variants": variants, "remaining": found, "tag_index_entries_not_found_by_owning_service": stale})
    return run.finish()


def _record_full_run(label, log, run_ids, reference_run, aborted=None):
    run = results.Run(f"{label}-TST-OPS-001", None, "fresh-copy run")
    problems = [f"step {e['step']} exit {e['exit']}" for e in log if e["exit"] not in (0,)]
    comparison = None
    if reference_run and "all" in run_ids:
        mine, theirs = statuses(results.load(run_ids["all"])), statuses(results.load(reference_run))
        comparison = {"reference": reference_run, "this_run": run_ids["all"],
                      "differences": {t: [theirs.get(t), mine.get(t)] for t in set(mine) | set(theirs) if mine.get(t) != theirs.get(t)}}
        if comparison["differences"]:
            problems.append(f"results differ from the reference run: {comparison['differences']}")
    if aborted:
        problems.append(aborted)
    run.record("TST-OPS-001", "repeatability", ["OPS-003"], [], "L5",
               "Unattended from a fresh copy: preflight → deploy → fixtures → full suite → experiments → cleanup verified; "
               "results match", "FAIL" if problems else "PASS", "; ".join(problems) or
               "every step exited 0; results match the reference run; cleanup verified", {"steps": log, "runs": run_ids,
                                                                                         "comparison": comparison})
    return run.finish()
