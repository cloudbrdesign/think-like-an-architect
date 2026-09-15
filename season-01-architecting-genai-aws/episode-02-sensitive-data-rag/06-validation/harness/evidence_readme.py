"""Generate the evidence bundle README from the bundled runs' results.json files — nothing typed by hand."""
import json
import os


def _load(root, run_id):
    path = os.path.join(root, run_id, "results.json")
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _table(document):
    rows = ["| Test | Status | Key observation |", "|---|---|---|"]
    for test in document["tests"]:
        observed = test["observed"].replace("|", "/").replace("\n", " ")
        rows.append(f"| `{test['test_id']}` | {test['status']} | {observed[:260]} |")
    return rows


def write(root, title, source_revision, normal_run, experiment_runs, extra_runs, notes):
    lines = [f"# {title}", "",
             f"Source revision `{source_revision}` · region us-east-1 · account identifiers redacted · synthetic data only.",
             "Portfolio evidence of the work performed, verified for this educational implementation under the tested "
             "conditions — not a certification, a compliance statement or a claim that any system is secure.", ""]
    lines += ["| Folder | What it is |", "|---|---|"]
    for run_id in [normal_run] + [f"{e}-{s}" for e in experiment_runs for s in ("baseline", "variant", "cleanup", "restored",
                                                                             "verdict")] + extra_runs:
        document = _load(root, run_id)
        if document:
            counts = document.get("counts", {})
            lines.append(f"| `{run_id}/` | {document.get('scope')} — PASS {counts.get('PASS', 0)} · FAIL "
                         f"{counts.get('FAIL', 0)} · ERROR {counts.get('ERROR', 0)} |")
        elif os.path.isdir(os.path.join(root, run_id)):
            lines.append(f"| `{run_id}/` | supporting evidence |")
    normal = _load(root, normal_run)
    if normal:
        lines += ["", f"## Validation suite — normal deployment (`{normal_run}`)", ""] + _table(normal)
    lines += ["", "## Failure experiments", ""]
    for experiment in experiment_runs:
        verdict = _load(root, f"{experiment}-verdict")
        if verdict:
            lines += _table(verdict)
            lines.append("")
    for run_id in extra_runs:
        document = _load(root, run_id)
        if document and document.get("tests"):
            lines += [f"## `{run_id}`", ""] + _table(document) + [""]
    lines += ["## Notes", ""] + [f"- {n}" for n in notes]
    with open(os.path.join(root, "README.md"), "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines).rstrip() + "\n")
