"""Component tests: strict tenant group claim parser (CTL-004, CH-12). Exactly one tenant, or deny."""
import unittest

import support  # noqa: F401  (import path)
from shared.reason_codes import Denied
from shared.tenant_claims import parse_tenant_group_claim


class TenantClaimParserTests(unittest.TestCase):
    def assertDenied(self, raw, code):
        with self.assertRaises(Denied) as caught:
            parse_tenant_group_claim(raw)
        self.assertEqual(caught.exception.reason.code, code, raw)

    def test_one_valid_tenant_group(self):
        self.assertEqual(parse_tenant_group_claim("[tenant-a]"), "tenant-a")
        self.assertEqual(parse_tenant_group_claim("[tenant-calderbay-2]"), "tenant-calderbay-2")

    def test_no_group_claim(self):
        self.assertDenied(None, "TENANT_CLAIM_MISSING")

    def test_empty_claim(self):
        self.assertDenied("", "TENANT_CLAIM_MISSING")
        self.assertDenied("[]", "TENANT_CLAIM_MISSING")

    def test_two_groups(self):
        self.assertDenied("[tenant-a tenant-b]", "TENANT_CLAIM_AMBIGUOUS")
        self.assertDenied("[tenant-a admins]", "TENANT_CLAIM_AMBIGUOUS")

    def test_malformed_claim(self):
        for raw in ('["tenant-a"]', "[tenant-a,tenant-b]", "tenant-a", "[tenant-a", "tenant-a]", "[tenant-a ]",
                    "[ tenant-a]", " [tenant-a]", "[tenant-a]\n", "[[tenant-a]]"):
            self.assertDenied(raw, "TENANT_CLAIM_AMBIGUOUS")

    def test_unexpected_type(self):
        for raw in (["tenant-a"], {"tenant-a": True}, 7):
            self.assertDenied(raw, "TENANT_CLAIM_AMBIGUOUS")

    def test_unexpected_tenant_syntax(self):
        for raw in ("[Tenant-A]", "[admins]", "[tenant-]", "[tenant_a]", "[tenant-a/b]", "[tenant-" + "x" * 41 + "]",
                    "[tenant-a;tenant-b]", "[ténant-a]"):
            self.assertDenied(raw, "TENANT_CLAIM_AMBIGUOUS")


if __name__ == "__main__":
    unittest.main()
