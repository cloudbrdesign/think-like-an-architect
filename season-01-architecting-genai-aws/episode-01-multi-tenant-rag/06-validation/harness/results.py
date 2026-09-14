"""Results in schema tla-validation-results/1: results.json, summary.md and evidence/<test-id>.json (redacted)."""
import json
import os
import subprocess

from harness.common import EPISODE, RESULTS, now_iso, redact

STATUSES = ("PASS", "FAIL", "ERROR", "NOT_RUN", "NOT_APPLICABLE")


def summary_row(test):
    """One summary.md row. The test ID is written as code: the validation plan is the single place a test ID is defined,
    and tools/traceability_check.py treats a bare ID in a table's first cell as a (duplicate) definition."""
    return (f"| `{test['test_id']}` | {', '.join(test['verifies'])} | {test['status']} | "
            f"{test['reason'].replace('|', '/')} | `{test['evidence'][0]}` |")


class Run:
    def __init__(self, run_id, target, suite):
        self.run_id, self.target, self.suite = run_id, target, suite
        self.directory = os.path.join(RESULTS, run_id)
        os.makedirs(os.path.join(self.directory, "evidence"), exist_ok=True)
        self.tests, self.started_at = [], now_iso()

    def record(self, test_id, suite, verifies, controls, level, expected, status, reason, observations,
               privileged=False, started_at=None):
        if status not in STATUSES:
            raise ValueError(status)
        evidence_file = f"evidence/{test_id}.json"
        entry = {"test_id": test_id, "suite": suite, "verifies": verifies, "controls": controls, "level": level,
                 "expected": expected, "status": status, "reason": reason, "privileged": privileged,
                 "evidence": [evidence_file], "started_at": started_at or now_iso(), "finished_at": now_iso()}
        with open(os.path.join(self.directory, evidence_file), "w") as handle:
            json.dump(redact({**entry, "observations": observations}), handle, indent=2, sort_keys=True, default=str)
        self.tests.append(entry)
        print(f"{status:<15} {test_id:<14} {reason}")
        return entry

    def finish(self, extra=None):
        commit = None
        try:
            commit = subprocess.run(["git", "-C", EPISODE, "rev-parse", "HEAD"], capture_output=True, text=True,
                                    timeout=5).stdout.strip() or None
        except Exception:  # noqa: BLE001
            pass
        target = self.target
        metadata = {"schema": "tla-validation-results/1", "run_id": self.run_id, "suite": self.suite,
                    "started_at": self.started_at, "finished_at": now_iso(), "harness_commit": commit,
                    "variant": getattr(target, "variant", None), "stack": getattr(target, "stack_name", None),
                    "region": getattr(target, "region", None), "account": "<account>",
                    "packages": {k: v["sha256"] for k, v in (getattr(target, "manifest", {}) or {}).get("packages", {}).items()},
                    **(extra or {})}
        counts = {s: sum(1 for t in self.tests if t["status"] == s) for s in STATUSES}
        json.dump(redact({**metadata, "counts": counts, "tests": self.tests}),
                  open(os.path.join(self.directory, "results.json"), "w"), indent=2, default=str)
        lines = [f"# Validation results — {self.run_id}", "",
                 f"Variant **{metadata['variant']}** · stack `{metadata['stack']}` · region {metadata['region']} · "
                 f"commit `{commit}` · {metadata['started_at']} → {metadata['finished_at']}", "",
                 " · ".join(f"{s} {n}" for s, n in counts.items()), "",
                 "| Test | Verifies | Status | Key observation | Evidence |", "|---|---|---|---|---|"]
        for t in self.tests:
            lines.append(summary_row(t))
        open(os.path.join(self.directory, "summary.md"), "w").write(redact("\n".join(lines)) + "\n")
        print(f"results: {os.path.relpath(self.directory, os.getcwd())} — " + ", ".join(f"{s} {n}" for s, n in counts.items() if n))
        if counts["ERROR"]:
            return 2
        if counts["FAIL"]:
            return 1
        return 0
