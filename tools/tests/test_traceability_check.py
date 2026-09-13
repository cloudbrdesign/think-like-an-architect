"""Traceability check tests: a synthetic engagement passes; each planted break in the chain is rejected."""
import contextlib
import io
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import traceability_check as tc  # noqa: E402

REQUIREMENTS = ("# Requirements\n\n"
                "| ID | Requirement | Rationale | Priority | Source | Verified by | Related decisions |\n"
                "|---|---|---|---|---|---|---|\n"
                "| SEC-001 | Fixture security requirement | fixture | MUST | fixture | TST-ISO-001 | ADR-001 |\n"
                "| OPS-001 | Fixture operational requirement | fixture | SHOULD | fixture | review | — |\n")
ADR_001 = ("# ADR-001 — Fixture decision\n\n## Controls\n\n"
           "| ID | Control | Enforcement point |\n|---|---|---|\n| CTL-001 | Fixture control | fixture component |\n")
PLAN = ("# Validation plan\n\n| ID | Verifies | Level | Type | Expected |\n|---|---|---|---|---|\n"
        "| TST-ISO-001 | SEC-001 | L3 | negative | refused |\n")
MATRIX_HEADER = ("| Requirement | Decision | Control | Test | Observed result | Evidence |\n"
                 "|---|---|---|---|---|---|\n")
ROW = "| SEC-001 | ADR-001 | CTL-001 | TST-ISO-001 | PASS | 07-evidence/tst-iso-001.txt |\n"


class Traceability(unittest.TestCase):
    def build(self, matrix_rows=ROW, requirements=REQUIREMENTS, adr=ADR_001, plan=PLAN, extra=None, matrix=True):
        root = tempfile.mkdtemp(prefix="tla-trace-")
        self.addCleanup(shutil.rmtree, root)
        files = {"02-requirements/REQUIREMENTS.md": requirements, "04-decisions/ADR-001.md": adr,
                 "06-validation/VALIDATION_PLAN.md": plan, "07-evidence/tst-iso-001.txt": "fixture output\n"}
        if matrix:
            files["06-validation/TRACEABILITY_MATRIX.md"] = MATRIX_HEADER + matrix_rows
        files.update(extra or {})
        for rel, text in files.items():
            path = os.path.join(root, rel)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(text)
        return root

    def violations(self, **kwargs):
        return tc.check(self.build(**kwargs))[0]

    def assertViolation(self, fragment, **kwargs):
        found = self.violations(**kwargs)
        self.assertTrue(any(fragment in v for v in found), f"expected '{fragment}' in {found}")

    def query(self, root, *args):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = tc.main([root, *args])
        return code, out.getvalue()

    # valid chain
    def test_valid_engagement_passes(self):
        violations, warnings, _ = tc.check(self.build())
        self.assertEqual((violations, warnings), ([], []))

    def test_why_query_answers_which_requirement_drove_the_decision(self):
        code, text = self.query(self.build(), "--why", "ADR-001")
        self.assertEqual(code, 0)
        self.assertIn("driven by: SEC-001", text)

    def test_proof_query_answers_which_test_demonstrates_the_requirement(self):
        code, text = self.query(self.build(), "--proof", "SEC-001")
        self.assertEqual(code, 0)
        self.assertIn("TST-ISO-001 · result PASS · evidence 07-evidence/tst-iso-001.txt", text)

    def test_review_rationale_accepted_without_test(self):
        row = ROW + "| OPS-001 | — | — | review: verified by inspection of the cleanup log | NOT RUN | — |\n"
        self.assertEqual(self.violations(matrix_rows=row), [])

    def test_untraced_test_is_a_warning_not_a_violation(self):
        plan = PLAN + "| TST-ISO-002 | SEC-001 | L3 | positive | allowed |\n"
        violations, warnings, _ = tc.check(self.build(plan=plan))
        self.assertEqual(violations, [])
        self.assertTrue(any("TST-ISO-002" in w for w in warnings))

    # planted breaks
    def test_undefined_decision_rejected(self):
        self.assertViolation("ADR-002 is referenced but never defined", matrix_rows=ROW.replace("ADR-001", "ADR-002"))

    def test_must_requirement_missing_from_matrix_rejected(self):
        requirements = REQUIREMENTS + "| SEC-002 | Second fixture requirement | fixture | MUST | fixture | — | — |\n"
        self.assertViolation("MUST requirement SEC-002 is missing", requirements=requirements)

    def test_requirement_without_test_or_review_rejected(self):
        self.assertViolation("neither a test nor a 'review:' rationale",
                             matrix_rows=ROW.replace("TST-ISO-001", "—"))

    def test_pass_without_existing_evidence_rejected(self):
        self.assertViolation("evidence not found", matrix_rows=ROW.replace("tst-iso-001.txt", "missing.txt"))

    def test_absolute_evidence_path_rejected(self):
        bad = ROW.replace("07-evidence/tst-iso-001.txt", "/Us" + "ers/someone/evidence.txt")
        self.assertViolation("not portable", matrix_rows=bad)

    def test_invalid_observed_result_rejected(self):
        self.assertViolation("observed result must be one of", matrix_rows=ROW.replace("| PASS |", "| OK |"))

    def test_duplicate_definition_rejected(self):
        plan = PLAN + "| CTL-001 | duplicate | L0 | static | none |\n"
        self.assertViolation("CTL-001 is defined more than once", plan=plan)

    def test_wrong_id_family_in_column_rejected(self):
        self.assertViolation("Decision column contains", matrix_rows=ROW.replace("| ADR-001 |", "| CTL-001 |"))

    def test_missing_matrix_rejected(self):
        self.assertViolation("exactly one TRACEABILITY_MATRIX.md is required", matrix=False)

    def test_wrong_matrix_header_rejected(self):
        root = self.build(extra={"06-validation/TRACEABILITY_MATRIX.md": "| Req | Test |\n|---|---|\n| SEC-001 | TST-ISO-001 |\n"})
        self.assertTrue(any("matrix header must be" in v for v in tc.check(root)[0]))


if __name__ == "__main__":
    unittest.main()
