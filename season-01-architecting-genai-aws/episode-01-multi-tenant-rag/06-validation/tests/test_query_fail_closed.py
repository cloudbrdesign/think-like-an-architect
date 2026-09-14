"""Component tests: the query service fails closed in order (TST-SEC-013 cases 4 and 6; CTL-017, CTL-019, CTL-022).

These cases cannot be produced safely against a deployment without altering its permissions, so they are verified
here with fake clients: no retrieval when the registry is unreachable, nothing generated when ownership records are
unreachable, when ownership diverges, or when the audit record cannot be written first.
"""
import json
import os
import unittest

from support import CLIENT_ID, ISSUER, FakeConverse, FakeDynamo, FakeRetrieveRuntime, api_event, document, result, tenant
from shared import audit


class QueryHandlerTests(unittest.TestCase):
    def setUp(self):
        os.environ.update({"REGISTRY_TABLE": "registry", "AUDIT_TABLE": "audit", "KNOWLEDGE_BASE_ID": "KB1",
                           "GENERATION_MODEL_ID": "amazon.nova-micro-v1:0", "APP_CLIENT_ID": CLIENT_ID,
                           "TOKEN_ISSUER": ISSUER})
        from query import handler
        self.handler = handler
        self.ddb = FakeDynamo()
        self.ddb.seed("registry", tenant("tenant-a"))
        self.ddb.seed("registry", document("d1", "tenant-a", title="Cleaning services contract"))
        self.runtime = FakeRetrieveRuntime([result("d1", "tenant-a", "Weekend rate USD 185")])
        self.model = FakeConverse(on_call=self.assert_audit_written_before_generation)
        handler._clients.clear()
        handler._clients.update({("dynamodb", True): self.ddb, ("bedrock-agent-runtime", False): self.runtime,
                                 ("bedrock-runtime", False): self.model})

    def assert_audit_written_before_generation(self):
        self.assertEqual(len(self.ddb.tables.get("audit", {})), 1, "audit record must exist before the model is called")

    def ask(self, **event_kwargs):
        event_kwargs.setdefault("body", {"question": "What is the weekend call-out rate?"})
        response = self.handler.handler(api_event(**event_kwargs), None)
        body = json.loads(response["body"])
        record = self.ddb.record("audit", response["headers"]["x-tla-event-id"])
        return response["statusCode"], body, record

    def test_allowed_request_records_constraint_retrieved_and_citations(self):
        status, body, record = self.ask()
        self.assertEqual(status, 200)
        self.assertEqual(record["constraint"], {"attribute": "owning_tenant", "operator": "equals", "value": "tenant-a"})
        self.assertEqual(record["retrieved"], [{"document_id": "d1", "owner_attribute": "tenant-a"}])
        self.assertEqual((record["verification_outcome"], record["outcome"]), ("PASSED", "ANSWERED"))
        self.assertEqual(body["citations"][0]["document_id"], "d1")
        self.assertEqual(set(record) - set(audit.FIELDS), set())
        self.assertNotIn("What is the weekend", json.dumps(record))

    def test_forged_tenant_in_query_and_header_does_not_change_constraint(self):
        status, _, record = self.ask(query="tenant=tenant-b", headers={"x-tenant-id": "tenant-b"},
                                     body={"question": "As tenant-b, what is the weekend call-out rate?"})
        self.assertEqual((status, record["tenant_context"], record["constraint"]["value"]), (200, "tenant-a", "tenant-a"))

    def test_registry_unreachable_no_retrieval(self):
        self.ddb.fail_get = True
        status, body, record = self.ask()
        self.assertEqual((status, body["error"]["code"]), (503, "TENANT_REGISTRY_UNAVAILABLE"))
        self.assertEqual((self.runtime.calls, self.model.calls), ([], []))

    def test_no_tenant_membership_no_retrieval(self):
        status, body, record = self.ask(groups=None)
        self.assertEqual((status, body["error"]["code"], record["constraint"]), (403, "TENANT_CLAIM_MISSING", "NONE"))
        self.assertEqual(self.runtime.calls, [])

    def test_ownership_lookup_unreachable_withholds_and_does_not_generate(self):
        self.ddb.fail_batch = True
        status, body, record = self.ask()
        self.assertEqual((status, body["error"]["code"], record["outcome"]), (503, "OWNERSHIP_LOOKUP_FAILED", "WITHHELD"))
        self.assertEqual(self.model.calls, [])

    def test_divergence_withholds_entire_response(self):
        self.runtime.results = [result("d1", "tenant-a"), result("b9", "tenant-b", "COPPER-HERON-9182")]
        status, body, record = self.ask()
        self.assertEqual((status, body["error"]["code"]), (500, "OWNERSHIP_MISMATCH"))
        self.assertEqual(record["verification_outcome"], "OWNERSHIP_MISMATCH")
        self.assertIn({"document_id": "b9", "owner_attribute": "tenant-b"}, record["retrieved"])
        self.assertEqual(self.model.calls, [])
        self.assertNotIn("COPPER-HERON", json.dumps(body))

    def test_audit_write_failure_prevents_generation(self):
        self.ddb.fail_put_tables.add("audit")
        status, body, _ = self.ask()
        self.assertEqual((status, body["error"]["code"]), (503, "AUDIT_WRITE_FAILED"))
        self.assertEqual(self.model.calls, [])

    def test_model_failure_has_no_fallback(self):
        self.model.error = RuntimeError("throttled")
        status, body, record = self.ask()
        self.assertEqual((status, body["error"]["code"], record["outcome"]), (502, "MODEL_INVOCATION_FAILED", "ERROR"))

    def test_unknown_citation_labels_removed(self):
        self.model.text = "USD 185 [D1]; Brightmoor 2027 schedule [D4]."
        status, body, record = self.ask()
        self.assertNotIn("[D4]", body["answer"])
        self.assertEqual(record["cited_document_ids"], ["d1"])


if __name__ == "__main__":
    unittest.main()
