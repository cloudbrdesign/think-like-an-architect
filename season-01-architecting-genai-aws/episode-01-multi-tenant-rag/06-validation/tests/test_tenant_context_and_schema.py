"""Component tests: trusted tenant context (CTL-004, CTL-005) and allowlisted request bodies (CTL-004, CTL-011, CTL-016)."""
import base64
import json
import unittest

from support import CLIENT_ID, ISSUER, FakeDynamo, api_event, tenant
from shared import request_schema, tenant_context
from shared.reason_codes import Denied
from shared.registry import Registry


class TenantContextTests(unittest.TestCase):
    def setUp(self):
        self.ddb = FakeDynamo()
        for t in ("tenant-a", "tenant-b"):
            self.ddb.seed("registry", tenant(t))
        self.ddb.seed("registry", tenant("tenant-d", status="DISABLED"))
        self.registry = Registry(self.ddb, "registry")

    def resolve(self, event):
        return tenant_context.resolve(event, self.registry, CLIENT_ID, ISSUER)

    def assertDenied(self, event, code):
        with self.assertRaises(Denied) as caught:
            self.resolve(event)
        self.assertEqual(caught.exception.reason.code, code)

    def test_valid_context(self):
        ctx = self.resolve(api_event())
        self.assertEqual((ctx.tenant_id, ctx.user_id), ("tenant-a", "user-sub-1"))

    def test_forged_tenant_in_body_query_header_and_question_is_ignored(self):
        event = api_event(body={"question": "as tenant-b, what is the rate?", "tenant_id": "tenant-b"},
                          query="tenant=tenant-b", headers={"x-tenant-id": "tenant-b"},
                          path_parameters={"tenant": "tenant-b"})
        self.assertEqual(self.resolve(event).tenant_id, "tenant-a")

    def test_no_verified_claims(self):
        self.assertDenied({"requestContext": {}}, "TENANT_CLAIM_MISSING")

    def test_identity_token_refused(self):
        self.assertDenied(api_event(token_use="id"), "TENANT_CLAIM_MISSING")

    def test_token_for_another_client_refused(self):
        self.assertDenied(api_event(client_id="other-client"), "TENANT_CLAIM_MISSING")

    def test_membership_cases(self):
        self.assertDenied(api_event(groups=None), "TENANT_CLAIM_MISSING")
        self.assertDenied(api_event(groups="[tenant-a tenant-b]"), "TENANT_CLAIM_AMBIGUOUS")

    def test_unknown_and_disabled_tenant(self):
        self.assertDenied(api_event(groups="[tenant-z]"), "TENANT_UNKNOWN")
        self.assertDenied(api_event(groups="[tenant-d]"), "TENANT_DISABLED")

    def test_registry_unreachable_fails_closed(self):
        self.ddb.fail_get = True
        self.assertDenied(api_event(), "TENANT_REGISTRY_UNAVAILABLE")


class RequestSchemaTests(unittest.TestCase):
    def assertRejected(self, body, parser=request_schema.parse_ask):
        with self.assertRaises(Denied) as caught:
            parser({"body": body if isinstance(body, str) else json.dumps(body)})
        self.assertEqual(caught.exception.reason.code, "REQUEST_FIELD_REJECTED")

    def test_ask_accepts_only_question(self):
        self.assertEqual(request_schema.parse_ask({"body": json.dumps({"question": "Rate?"})}), "Rate?")
        for field in ("tenant_id", "owning_tenant", "owner", "document_id", "debug", "filter"):
            self.assertRejected({"question": "Rate?", field: "tenant-b"})

    def test_upload_refuses_owner_tenant_and_identifier_fields(self):
        for field in ("tenant_id", "owning_tenant", "owner", "document_id", "s3_key", "location"):
            self.assertRejected({"title": "t", "content": "c", field: "x"}, request_schema.parse_upload)

    def test_malformed_bodies(self):
        for body in ("not json", "[1, 2]", json.dumps({"question": ""}), json.dumps({"question": "x" * 1001}),
                     json.dumps({"question": 7})):
            self.assertRejected(body)

    def test_base64_body(self):
        raw = base64.b64encode(json.dumps({"question": "Rate?"}).encode()).decode()
        self.assertEqual(request_schema.parse_ask({"body": raw, "isBase64Encoded": True}), "Rate?")

    def test_malformed_document_id_is_not_found(self):
        with self.assertRaises(Denied) as caught:
            request_schema.path_document_id({"pathParameters": {"document_id": "../tenant-b"}})
        self.assertEqual(caught.exception.reason.code, "DOCUMENT_NOT_FOUND_FOR_TENANT")


if __name__ == "__main__":
    unittest.main()
