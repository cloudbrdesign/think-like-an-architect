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


if __name__ == "__main__":
    unittest.main()
