"""Component tests: ingestion attribution (CTL-011, CTL-012, CTL-013, CTL-014) including TST-ASM-010 (a) and
TST-SEC-013 case 7 — inconsistent attribution is quarantined and never indexed."""
import json
import os
import unittest
from unittest import mock

from support import CLIENT_ID, ISSUER, FakeAgent, FakeDynamo, FakeS3, api_event, document, tenant
from shared import ownership
from shared.tenant_context import TenantContext

CTX_A = TenantContext("tenant-a", "user-sub-1", CLIENT_ID, ISSUER)
DOC_ID = "0b6f1f5e-8f7a-4c1e-9d2a-3c4b5a6d7e8f"


class AttributionGateTests(unittest.TestCase):
    def good(self):
        record = {"owner": "tenant-a", "document_id": DOC_ID}
        return record, ownership.storage_key("tenant-a", DOC_ID), ownership.index_attributes("tenant-a", DOC_ID)

    def test_consistent_attribution_passes(self):
        ownership.attribution_gate(CTX_A, *self.good())

    def test_every_inconsistency_is_a_conflict(self):
        record, key, attributes = self.good()
        cases = {
            "record owner differs": ({**record, "owner": "tenant-b"}, key, attributes),
            "storage key tenant differs": (record, ownership.storage_key("tenant-b", DOC_ID), attributes),
            "attribute owner differs": (record, key, ownership.index_attributes("tenant-b", DOC_ID)),
            "attribute missing": (record, key, attributes[1:]),
            "record missing": (None, key, attributes),
            "document id differs": ({**record, "document_id": "other"}, key, attributes),
            "malformed key": (record, "uploads/anything.md", attributes),
            "invalid tenant value": ({**record, "owner": "Tenant-A"}, key, attributes),
        }
        for name, args in cases.items():
            with self.subTest(name), self.assertRaises(ownership.AttributionConflict):
                ownership.attribution_gate(CTX_A, *args)


class IngestionHandlerTests(unittest.TestCase):
    def setUp(self):
        os.environ.update({"REGISTRY_TABLE": "registry", "AUDIT_TABLE": "audit", "DOCUMENT_BUCKET": "docs",
                           "KNOWLEDGE_BASE_ID": "KB1", "DATA_SOURCE_ID": "DS1", "APP_CLIENT_ID": CLIENT_ID,
                           "TOKEN_ISSUER": ISSUER})
        from ingestion import handler
        self.handler = handler
        self.ddb, self.agent, self.s3 = FakeDynamo(), FakeAgent(), FakeS3()
        for t in ("tenant-a", "tenant-b"):
            self.ddb.seed("registry", tenant(t))
        handler._clients.clear()
        handler._clients.update({("dynamodb", True): self.ddb, ("bedrock-agent", False): self.agent,
                                 ("s3", False): self.s3})

    def call(self, event):
        response = self.handler.handler(event, None)
        return response["statusCode"], json.loads(response["body"])

    def test_upload_assigns_owner_key_and_attributes_from_context(self):
        status, body = self.call(api_event(route="POST /documents",
                                           body={"title": "Window schedule", "content": "Owner: Brightmoor Services"}))
        self.assertEqual(status, 202)
        record = self.ddb.record("registry", f"DOC#{body['document_id']}")
        self.assertEqual((record["owner"], record["status"]), ("tenant-a", "INDEXING"))
        self.assertTrue(record["s3_key"].startswith("tenants/tenant-a/documents/"))
        attributes = self.agent.ingested[0]["documents"][0]["metadata"]["inlineAttributes"]
        self.assertEqual(attributes, ownership.index_attributes("tenant-a", body["document_id"]))
        self.assertIn("s3://docs/tenants/tenant-a/", self.agent.ingested[0]["documents"][0]["content"]["custom"]["s3Location"]["uri"])

    def test_owner_fields_refused_and_nothing_stored(self):
        for field in ("owning_tenant", "tenant_id", "owner", "document_id"):
            status, body = self.call(api_event(route="POST /documents", body={"title": "t", "content": "c", field: "tenant-b"}))
            self.assertEqual((status, body["error"]["code"]), (400, "REQUEST_FIELD_REJECTED"))
        self.assertEqual((self.s3.objects, self.agent.ingested), ({}, []))

    def test_inconsistent_attribution_is_quarantined_and_never_indexed(self):
        with mock.patch.object(ownership, "index_attributes", lambda t, d: [
                {"key": "owning_tenant", "value": {"type": "STRING", "stringValue": "tenant-b"}},
                {"key": "document_id", "value": {"type": "STRING", "stringValue": d}}]):
            status, body = self.call(api_event(route="POST /documents", body={"title": "t", "content": "c"}))
        self.assertEqual((status, body["error"]["code"]), (409, "INGESTION_ATTRIBUTION_CONFLICT"))
        self.assertEqual(self.agent.ingested, [])
        records = [r for r in self.ddb.tables["registry"] if r.startswith("DOC#")]
        self.assertEqual(self.ddb.record("registry", records[0])["status"], "QUARANTINED")
        audit = list(self.ddb.tables["audit"].values())[0]
        self.assertEqual(audit["reason_code"]["S"], "INGESTION_ATTRIBUTION_CONFLICT")

    def test_other_tenants_document_is_not_found_for_open_and_delete(self):
        self.ddb.seed("registry", document(DOC_ID, "tenant-b"))
        for route in ("GET /documents/{document_id}", "DELETE /documents/{document_id}"):
            status, body = self.call(api_event(route=route, path_parameters={"document_id": DOC_ID}))
            self.assertEqual((status, body["error"]["code"]), (404, "DOCUMENT_NOT_FOUND_FOR_TENANT"))
        self.assertEqual(self.ddb.record("registry", f"DOC#{DOC_ID}")["status"], "AVAILABLE")
        self.assertEqual(self.agent.deleted, [])

    def test_delete_own_document_propagates(self):
        self.ddb.seed("registry", document(DOC_ID, "tenant-a"))
        status, body = self.call(api_event(route="DELETE /documents/{document_id}", path_parameters={"document_id": DOC_ID}))
        self.assertEqual((status, body["status"]), (202, "DELETING"))
        self.assertEqual(len(self.agent.deleted), 1)
        self.assertEqual(self.s3.deleted, [("docs", f"tenants/tenant-a/documents/{DOC_ID}/source.md")])

    def test_disabled_tenant_cannot_upload(self):
        self.ddb.seed("registry", tenant("tenant-a", status="DISABLED"))
        status, body = self.call(api_event(route="POST /documents", body={"title": "t", "content": "c"}))
        self.assertEqual((status, body["error"]["code"]), (403, "TENANT_DISABLED"))
        self.assertEqual(self.s3.objects, {})


if __name__ == "__main__":
    unittest.main()
