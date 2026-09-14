"""Tests of the harness's own observation rules. A wrong observation rule produces false passes or false failures.

Both rules below were corrected after the first E4 run:
  - canaries count only document-scoped markers, so a question that names a bare marker cannot look like a leak;
  - redaction removes account numbers but keeps UUIDs (event IDs) intact.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")))

from harness import canary  # noqa: E402
from harness.common import redact  # noqa: E402


class CanaryRuleTests(unittest.TestCase):
    def test_echoed_bare_marker_from_a_question_is_not_a_leak(self):
        self.assertEqual(canary.foreign_hits("tenant-a", {"answer": "I cannot find COPPER-HERON-9182 in your documents."}), {})

    def test_document_marker_from_another_tenant_is_a_leak(self):
        self.assertEqual(canary.foreign_hits("tenant-a", {"answer": "USD 240 (COPPER-HERON-9182-B1)"}), {"tenant-b": 1})

    def test_own_marker_is_not_a_leak(self):
        self.assertEqual(canary.foreign_hits("tenant-a", {"citations": [{"title": "JUNIPER-LANTERN-4471-A1"}]}), {})

    def test_every_fixture_document_marker_is_suffixed(self):
        fixtures = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "fixtures", "documents")
        for directory, _, files in os.walk(fixtures):
            for name in files:
                text = open(os.path.join(directory, name), encoding="utf-8").read()
                for prefix in canary.CANARIES.values():
                    bare = text.count(prefix) - sum(canary.document_markers(text).values())
                    self.assertLessEqual(bare, 0, f"{name} contains an unsuffixed {prefix}")


class RedactionTests(unittest.TestCase):
    def test_account_numbers_redacted_everywhere(self):
        self.assertEqual(redact("arn:aws:iam::123456789012:role/x"), "arn:aws:iam::<account>:role/x")
        self.assertEqual(redact("tla-s01e01-normal-docs-123456789012"), "tla-s01e01-normal-docs-<account>")

    def test_uuid_kept_whole(self):
        event_id = "2bd85928-f35a-46c8-a63c-123456789012"
        self.assertEqual(redact(f"event {event_id} in 123456789012"), f"event {event_id} in <account>")


class TimingCaptureTests(unittest.TestCase):
    """NFR-001 evidence capture (corrected after the E4 run, where started_at equalled finished_at)."""

    def test_sequential_tests_record_real_start_times(self):
        import tempfile
        import time as _time
        from harness import results
        with tempfile.TemporaryDirectory() as tmp:
            original = results.RESULTS
            results.RESULTS = tmp
            try:
                run = results.Run("timing-test", None, "unit")
                first = run.record("TST-ISO-001", "unit", [], [], "-", "e", "PASS", "r", {})
                _time.sleep(1.1)
                second = run.record("TST-ISO-002", "unit", [], [], "-", "e", "PASS", "r", {})
            finally:
                results.RESULTS = original
        self.assertEqual(second["started_at"], first["finished_at"])
        self.assertLess(second["started_at"], second["finished_at"])

    def test_response_summary_carries_client_elapsed_time(self):
        from harness.client import Response
        self.assertEqual(Response(200, {}, {"x-tla-event-id": "e"}, elapsed_ms=1234).summary()["client_elapsed_ms"], 1234)

    def test_audit_view_includes_server_latency(self):
        from harness.context import audit_view
        self.assertEqual(audit_view({"latency_ms": 870})["latency_ms"], 870)


class SummaryFormatTests(unittest.TestCase):
    def test_summary_rows_do_not_define_test_ids(self):
        import re
        from harness.results import summary_row
        row = summary_row({"test_id": "TST-ISO-003", "verifies": ["SEC-001"], "status": "PASS", "reason": "a | b",
                           "evidence": ["evidence/TST-ISO-003.json"]})
        first_cell = row.strip()[1:-1].split("|")[0].strip()
        self.assertIsNone(re.fullmatch(r"TST-[A-Z]+-\d{3}", first_cell))
        self.assertEqual(first_cell, "`TST-ISO-003`")


if __name__ == "__main__":
    unittest.main()
