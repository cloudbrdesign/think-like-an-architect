"""Fill the traceability matrix's result and evidence columns from executed runs only.

A requirement row becomes PASS only if every test it names was executed and passed; FAIL if any executed test failed;
rows proved by design or configuration review stay marked as review, never PASS. Nothing is inferred.
"""
import json
import os
import re

from harness.common import VALIDATION

MATRIX = os.path.join(VALIDATION, "TRACEABILITY_MATRIX.md")
TEST_ID = re.compile(r"TST-[A-Z]+-\d{3}")


def collect(evidence_root, run_ids):
    """{test_id: (status, relative evidence path)} from bundled runs; later runs never override an earlier FAIL."""
    found = {}
    for run_id in run_ids:
        path = os.path.join(evidence_root, run_id, "results.json")
        with open(path, encoding="utf-8") as handle:
            document = json.load(handle)
        for test in document["tests"]:
            if not TEST_ID.fullmatch(test["test_id"]):
                continue
            evidence = f"07-evidence/{os.path.basename(os.path.normpath(evidence_root))}/{run_id}/{test['evidence']}"
            if found.get(test["test_id"], ("PASS",))[0] != "FAIL":
                found[test["test_id"]] = (test["status"], evidence)
    return found


def update(evidence_root, run_ids, state_lines):
    results = collect(evidence_root, run_ids)
    with open(MATRIX, encoding="utf-8") as handle:
        lines = handle.read().splitlines()
    output, rows = [], 0
    for line in lines:
        cells = [c.strip() for c in line.strip().strip("|").split("|")] if line.startswith("| ") else []
        if len(cells) == 6 and re.fullmatch(r"(BUS|FUN|SEC|DATA|NFR|OPS|CMP)-\d{3}", cells[0]):
            rows += 1
            tests = TEST_ID.findall(cells[3])
            if not tests:
                cells[4], cells[5] = "NOT RUN", "—"        # proved by review, not by an executed test
            else:
                missing = [t for t in tests if t not in results]
                failed = [t for t in tests if t in results and results[t][0] != "PASS"]
                cells[4] = "NOT RUN" if missing else ("FAIL" if failed else "PASS")
                cells[5] = ", ".join(results[t][1] for t in tests if t in results) or "—"
            line = "| " + " | ".join(cells) + " |"
        output.append(line)
    text = "\n".join(output) + "\n"
    start = text.index("**State:**")
    end = text.index("| Requirement |")
    text = text[:start] + "\n".join(state_lines) + "\n\n" + text[end:]
    with open(MATRIX, "w", encoding="utf-8") as handle:
        handle.write(text)
    return {"rows": rows, "tests_with_results": len(results),
            "statuses": {t: s for t, (s, _) in sorted(results.items())}}
