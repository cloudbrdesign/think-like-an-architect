"""The ingestion job with fakes over the real synthetic corpus: quarantine, special-category exclusion, routing."""
import json
import os
import unittest

import support
from ingestion import handler

FIXTURES = os.path.join(support.EPISODE, "06-validation", "fixtures")
RECORDS = {r["document_id"]: r for r in json.load(open(os.path.join(FIXTURES, "classification_records.json")))["records"]}


class Records:
    def read(self, document_id):
        return open(os.path.join(FIXTURES, "records", f"{document_id}.md"), encoding="utf-8").read()


class Storage:
    def __init__(self):
        self.objects = {}

    def uri(self, tier, key):
        return f"s3://{tier}/{key}"

    def put(self, tier, key, body):
        self.objects[(tier, key)] = body


class Agent:
    def __init__(self):
        self.ingested = []

    def ingest_knowledge_base_documents(self, knowledgeBaseId, dataSourceId, documents):
        self.ingested += [(knowledgeBaseId, d) for d in documents]

    def get_knowledge_base_documents(self, knowledgeBaseId, dataSourceId, documentIdentifiers):
        return {"documentDetails": [{"identifier": i, "status": "INDEXED"} for i in documentIdentifiers]}


class IngestionJob(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.storage, cls.agent, cls.audit = Storage(), Agent(), support.FakeAudit()
        cls.report = handler.run({"document_ids": sorted(RECORDS)}, classification=support.FakeClassification(RECORDS),
                                 records=Records(), storage=cls.storage, agent=cls.agent,
                                 knowledge_bases={"shared": ("KB-S", "DS-S"), "restricted": ("KB-R", "DS-R")},
                                 audit=cls.audit, deployment="test", sleep=lambda s: None)

    def test_expected_tier_inventory(self):
        self.assertEqual(sorted(self.report["objects"]["restricted"]), ["D-04-S2", "D-05-S1"])
        self.assertEqual(sorted(self.report["objects"]["shared"]), [
            "D-01-S1", "D-01-S2", "D-02-S1", "D-02-S2", "D-03-S1", "D-03-S2", "D-03-S3", "D-03-S4", "D-04-S1",
            "D-06-S1", "D-07-S1", "D-08-S1", "D-12-S1", "D-13-S1", "D-14-S1"])

    def test_quarantine_report(self):
        self.assertEqual(sorted((q["document_id"], q["reason"]) for q in self.report["quarantine"]), [
            ("D-09", "LABEL_MISSING"), ("D-10", "LABEL_INVALID"), ("D-11", "SCOPE_MISSING"), ("D-15", "LABEL_INVALID")])

    def test_special_category_never_written_or_ingested(self):
        self.assertEqual(self.report["special_category_excluded"], ["D-04-S3"])
        everything = json.dumps([list(self.storage.objects), list(self.storage.objects.values()), self.agent.ingested,
                                 self.audit.items])
        self.assertNotIn("CANARY-SPECIAL-SI0417-MED", everything)
        self.assertNotIn("sections/D-04/S3.txt", everything)

    def test_quarantined_canaries_written_nowhere(self):
        written = json.dumps(list(self.storage.objects.values()))
        for canary in ("CANARY-UNLABELLED-TOOLS", "CANARY-MALFORMED-SUPPLIER", "CANARY-MALFORMED-NOSCOPE",
                       "CANARY-MALFORMED-LOWERCASE"):
            self.assertNotIn(canary, written)

    def test_restricted_objects_go_only_to_the_restricted_knowledge_base(self):
        for kb, document in self.agent.ingested:
            attributes = {a["key"]: a["value"]["stringValue"] for a in document["metadata"]["inlineAttributes"]}
            self.assertEqual(kb == "KB-R", attributes["label"] == "RESTRICTED")
            self.assertEqual(set(attributes), {"document_id", "section_id", "label", "scope", "record_version"})

    def test_text_claim_does_not_classify(self):
        d14 = [d for _, d in self.agent.ingested if d["content"]["custom"]["customDocumentIdentifier"]["id"] == "D-14-S1"][0]
        attributes = {a["key"]: a["value"]["stringValue"] for a in d14["metadata"]["inlineAttributes"]}
        self.assertEqual((attributes["label"], attributes["scope"]), ("CONFIDENTIAL", "BID-ORION"))

    def test_report_is_content_free(self):
        dumped = json.dumps(self.audit.items)
        self.assertNotIn("CANARY-", dumped)
        self.assertNotIn("Orion", dumped)


if __name__ == "__main__":
    unittest.main()
