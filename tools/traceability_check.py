#!/usr/bin/env python3
"""Think Like an Architect — traceability check (Python standard library only).

The chain every engagement must support:
  business problem → requirement → architecture decision → implementation control → validation test
  → observed result → portfolio evidence

IDs are used only where they improve traceability:
  requirements / assumptions  BUS|FUN|NFR|SEC|DATA|OPS|CMP|CON|ASM-NNN   first cell of a table row
  decisions                   ADR-NNN                                    a heading such as "# ADR-001 — title"
  controls                    CTL-NNN                                    first cell of a table row
  tests                       TST-AREA-NNN                               first cell of a table row
The matrix is TRACEABILITY_MATRIX.md with exactly these columns:
  | Requirement | Decision | Control | Test | Observed result | Evidence |

Usage:
  python3 tools/traceability_check.py <engagement-dir>                  validate the chain
  python3 tools/traceability_check.py <engagement-dir> --why ADR-001     which requirements drove this decision?
  python3 tools/traceability_check.py <engagement-dir> --proof SEC-001   which tests demonstrate this requirement?
Exit: 0 pass · 1 violations (or nothing traced for a query) · 2 usage error
"""
import argparse
import os
import re
import sys

REQ = r"(?:BUS|FUN|NFR|SEC|DATA|OPS|CMP|CON|ASM)-\d{3}"
ADR = r"ADR-\d{3}"
CTL = r"CTL-\d{3}"
TST = r"TST-[A-Z]+-\d{3}"
ID_RE = re.compile(rf"\b(?:{REQ}|{ADR}|{CTL}|{TST})\b")
COLUMN_FAMILY = {0: REQ, 1: ADR, 2: CTL, 3: TST}
MATRIX_NAME = "TRACEABILITY_MATRIX.md"
MATRIX_HEADER = ["Requirement", "Decision", "Control", "Test", "Observed result", "Evidence"]
RESULTS = ("NOT RUN", "PASS", "FAIL", "NOT VERIFIED", "NOT APPLICABLE")
SEPARATOR_RE = re.compile(r"^:?-{3,}:?$")


def table_cells(line):
    stripped = line.strip()
    if len(stripped) < 2 or not (stripped.startswith("|") and stripped.endswith("|")):
        return None
    return [cell.strip() for cell in stripped[1:-1].split("|")]


def is_separator(row):
    return all(SEPARATOR_RE.match(cell) for cell in row if cell)


def markdown_files(root):
    found = []
    for directory, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        found += [os.path.relpath(os.path.join(directory, n), root).replace(os.sep, "/") for n in files if n.endswith(".md")]
    return sorted(found)


def collect(root):
    definitions, must, matrices = {}, set(), []
    for rel in markdown_files(root):
        if os.path.basename(rel) == MATRIX_NAME:
            matrices.append(rel)
            continue
        with open(os.path.join(root, rel), encoding="utf-8") as handle:
            lines = handle.read().splitlines()
        header = None
        for line in lines:
            heading = re.match(rf"^#{{1,3}}\s+({ADR})\b", line)
            if heading:
                definitions.setdefault(heading.group(1), []).append(rel)
            row = table_cells(line)
            if row is None:
                header = None
                continue
            if is_separator(row):
                continue
            if header is None:
                header = row
                continue
            if re.fullmatch(rf"{REQ}|{CTL}|{TST}", row[0]):
                definitions.setdefault(row[0], []).append(rel)
                if "Priority" in header:
                    index = header.index("Priority")
                    if index < len(row) and row[index].upper() == "MUST" and not row[0].startswith("ASM"):
                        must.add(row[0])
    return definitions, must, matrices


def read_matrix(root, rel):
    rows, errors, header = [], [], None
    with open(os.path.join(root, rel), encoding="utf-8") as handle:
        for number, line in enumerate(handle.read().splitlines(), 1):
            row = table_cells(line)
            if row is None or is_separator(row):
                continue
            if header is None:
                header = row
                if header != MATRIX_HEADER:
                    errors.append(f"{rel}:{number}: matrix header must be | {' | '.join(MATRIX_HEADER)} |")
                continue
            if len(row) != len(MATRIX_HEADER):
                errors.append(f"{rel}:{number}: expected {len(MATRIX_HEADER)} columns, found {len(row)}")
                continue
            rows.append((number, row))
    if header is None:
        errors.append(f"{rel}: no matrix table found")
    return rows, errors


def portable(path):
    return not (path.startswith(("/", "~")) or re.match(r"^[A-Za-z]:", path) or "\\" in path or ".." in path.split("/"))


def check(root):
    definitions, must, matrices = collect(root)
    violations = [f"{i} is defined more than once: {', '.join(files)}" for i, files in sorted(definitions.items())
                  if len(files) > 1]
    if len(matrices) != 1:
        return violations + [f"exactly one {MATRIX_NAME} is required (found {len(matrices)})"], [], []
    matrix = matrices[0]
    rows, errors = read_matrix(root, matrix)
    violations += errors
    trace, covered, traced_tests = [], set(), set()
    for number, row in rows:
        where = f"{matrix}:{number}"
        ids = {}
        for column, family in COLUMN_FAMILY.items():
            found = ID_RE.findall(row[column])
            wrong = [x for x in found if not re.fullmatch(family, x)]
            if wrong:
                violations.append(f"{where}: {MATRIX_HEADER[column]} column contains {wrong}")
            ids[column] = [x for x in found if re.fullmatch(family, x)]
            violations += [f"{where}: {x} is referenced but never defined" for x in ids[column] if x not in definitions]
        if not ids[0]:
            violations.append(f"{where}: row has no requirement")
        review = row[3].lower().startswith("review:")
        if not ids[3] and not review:
            violations.append(f"{where}: {', '.join(ids[0]) or 'row'} has neither a test nor a 'review:' rationale")
        result = row[4]
        if result not in RESULTS:
            violations.append(f"{where}: observed result must be one of {list(RESULTS)}")
        evidence = [e.strip().strip("`") for e in row[5].split(",") if e.strip() not in ("", "—", "-")]
        if result in ("PASS", "FAIL"):
            if not evidence:
                violations.append(f"{where}: a {result} result requires evidence")
            for item in evidence:
                if not portable(item):
                    violations.append(f"{where}: evidence path is not portable: {item}")
                elif not os.path.exists(os.path.join(root, item)):
                    violations.append(f"{where}: evidence not found: {item}")
        covered.update(ids[0])
        traced_tests.update(ids[3])
        trace.append({"requirements": ids[0], "decisions": ids[1], "controls": ids[2], "tests": ids[3],
                      "review": row[3] if review else None, "result": result, "evidence": evidence})
    violations += [f"MUST requirement {r} is missing from the traceability matrix" for r in sorted(must - covered)]
    warnings = [f"test {t} is defined but not traced to a requirement"
                for t in sorted(d for d in definitions if re.fullmatch(TST, d)) if t not in traced_tests]
    return violations, warnings, trace


def main(argv=None):
    parser = argparse.ArgumentParser(description="Traceability check")
    parser.add_argument("root")
    query = parser.add_mutually_exclusive_group()
    query.add_argument("--why", help="decision ID: which requirements drove it?")
    query.add_argument("--proof", help="requirement ID: which tests demonstrate it?")
    args = parser.parse_args(argv)
    if not os.path.isdir(args.root):
        print(f"ERROR  not a directory: {args.root}")
        return 2
    violations, warnings, trace = check(args.root)
    if args.why:
        drivers = sorted({r for t in trace if args.why in t["decisions"] for r in t["requirements"]})
        print(f"{args.why} is driven by: {', '.join(drivers) if drivers else 'NOTHING TRACED'}")
        return 0 if drivers else 1
    if args.proof:
        rows = [t for t in trace if args.proof in t["requirements"]]
        for t in rows:
            print(f"{args.proof}: {', '.join(t['tests']) or t['review']} · result {t['result']} · "
                  f"evidence {', '.join(t['evidence']) or '—'}")
        if not rows:
            print(f"{args.proof}: NOTHING TRACED")
        return 0 if rows else 1
    for violation in violations:
        print(f"VIOLATION  {violation}")
    for warning in warnings:
        print(f"WARNING    {warning}")
    print(f"traceability check: {'PASS' if not violations else 'FAIL'} — {len(violations)} violation(s), "
          f"{len(warnings)} warning(s)")
    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main())
