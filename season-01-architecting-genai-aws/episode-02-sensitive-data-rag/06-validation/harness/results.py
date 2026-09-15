"""Results and evidence. Only executed tests are recorded; nothing is pre-filled. Evidence is redacted before writing."""
import json
import os

from harness.common import RESULTS, now_iso, redact

STATUSES = ("PASS", "FAIL", "ERROR")


class Run:
    def __init__(self, run_id, target, scope):
        self.run_id, self.scope = run_id, scope
        self.directory = os.path.join(RESULTS, run_id)
        os.makedirs(os.path.join(self.directory, "evidence"), exist_ok=True)
        self.meta = {"run_id": run_id, "scope": scope, "started_at": now_iso(),
                     "deployment": getattr(target, "stack_name", None), "variant": getattr(target, "variant", None),
                     "region": getattr(target, "region", None)}
        self.tests = []

    def record(self, test_id, category, verifies, controls, level, expected, status, observed, evidence,
               privileged=False):
        if status not in STATUSES:
            raise ValueError(status)
        entry = {"test_id": test_id, "category": category, "verifies": verifies, "controls": controls, "level": level,
                 "expected": expected, "status": status, "observed": observed, "privileged_observation": privileged,
                 "recorded_at": now_iso(), "evidence": f"evidence/{test_id}.json"}
        self.tests = [t for t in self.tests if t["test_id"] != test_id] + [entry]
        with open(os.path.join(self.directory, "evidence", f"{test_id}.json"), "w", encoding="utf-8") as handle:
            json.dump(redact({**entry, "observations": evidence}), handle, indent=2, sort_keys=True, default=str)
        print(f"{status:5}  {test_id:14} {observed[:150]}")
        return status

    def attach(self, name, data):
        with open(os.path.join(self.directory, name), "w", encoding="utf-8") as handle:
            json.dump(redact(data), handle, indent=2, sort_keys=True, default=str)

    def finish(self, extra=None):
        counts = {s: sum(1 for t in self.tests if t["status"] == s) for s in STATUSES}
        document = {**self.meta, "finished_at": now_iso(), "counts": counts, **(extra or {}),
                    "tests": sorted(self.tests, key=lambda t: t["test_id"])}
        with open(os.path.join(self.directory, "results.json"), "w", encoding="utf-8") as handle:
            json.dump(redact(document), handle, indent=2, sort_keys=True, default=str)
        lines = [f"# Run {self.run_id}", "", f"- Deployment: `{self.meta['deployment']}` (variant `{self.meta['variant']}`)",
                 f"- Started {self.meta['started_at']} · finished {document['finished_at']}",
                 f"- PASS {counts['PASS']} · FAIL {counts['FAIL']} · ERROR {counts['ERROR']}", "",
                 "| Test | Status | Observed |", "|---|---|---|"]
        lines += [f"| `{t['test_id']}` | {t['status']} | {redact(t['observed']).replace('|', '/')[:220]} |"
                  for t in document["tests"]]
        with open(os.path.join(self.directory, "summary.md"), "w", encoding="utf-8") as handle:
            handle.write("\n".join(lines) + "\n")
        print(f"run {self.run_id}: PASS {counts['PASS']} · FAIL {counts['FAIL']} · ERROR {counts['ERROR']}")
        return 0 if counts["PASS"] == len(self.tests) and self.tests else 1


def load(run_id):
    path = os.path.join(RESULTS, run_id, "results.json")
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)
