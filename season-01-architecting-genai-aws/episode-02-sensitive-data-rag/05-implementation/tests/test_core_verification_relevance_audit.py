"""Before-generation verification (CTL-014), relevance (TS-E02-07) and the content-free audit record (CTL-018)."""
import inspect
import unittest

import support
from core import audit_record, eligibility as e, relevance, verification as v

RECORDS = {"D-03": support.record(),
           "D-04": support.record(document_id="D-04", sections=[
               {"section_id": "S2", "title": "W", "label": "RESTRICTED", "scope": "SI-0417", "special_category": False},
               {"section_id": "S3", "title": "M", "label": "RESTRICTED", "scope": "SI-0417", "special_category": True}]),
           "D-05": support.record(document_id="D-05", document_label="RESTRICTED", document_scope="HR-2031", sections=[
               {"section_id": "S1", "title": "C", "label": None, "scope": None, "special_category": False}])}


def chunk(document_id="D-03", section_id="S4", label="CONFIDENTIAL", scope="BID-ORION", version="1", tier="shared",
          score=0.8, chunk_id=None):
    return v.RetrievedChunk(chunk_id or f"{document_id}-{section_id}-{label}-{score}", tier, document_id, section_id,
                            label, scope, version, score, "text")


def decision(domains=(), cases=()):
    return e.allow("sub", domains, cases, 1, 1)


class Verification(unittest.TestCase):
    def reason(self, d, c, records=RECORDS):
        result = v.verify(d, [c], records)
        return result.mismatches[0][1] if result.mismatches else None

    def test_pass(self):
        result = v.verify(decision(["BID-ORION"]), [chunk()], RECORDS)
        self.assertEqual((result.status, len(result.verified)), (v.PASS, 1))

    def test_indexed_label_differs_from_current_record(self):
        self.assertEqual(self.reason(decision(), chunk(label="INTERNAL", scope="NONE")), v.LABEL_MISMATCH)

    def test_scope_mismatch(self):
        self.assertEqual(self.reason(decision(["FIN-REPORTING"]), chunk(scope="FIN-REPORTING")), v.SCOPE_MISMATCH)

    def test_version_mismatch_after_reclassification(self):
        self.assertEqual(self.reason(decision(["BID-ORION"]), chunk(version="0")), v.VERSION_MISMATCH)

    def test_special_category_never_passes(self):
        self.assertEqual(self.reason(decision([], ["SI-0417"]), chunk("D-04", "S3", "RESTRICTED", "SI-0417",
                                                                       tier="restricted")), v.SPECIAL_CATEGORY)

    def test_wrong_tier(self):
        self.assertEqual(self.reason(decision([], ["SI-0417"]), chunk("D-04", "S2", "RESTRICTED", "SI-0417",
                                                                       tier="shared")), v.WRONG_TIER)

    def test_correct_tier_is_not_authorization(self):
        """P-05 holds SI-0417; an HR-2031 chunk from the restricted tier is still not eligible."""
        self.assertEqual(self.reason(decision([], ["SI-0417"]), chunk("D-05", "S1", "RESTRICTED", "HR-2031",
                                                                       tier="restricted")), v.NOT_ELIGIBLE)

    def test_missing_record_and_attributes(self):
        self.assertEqual(self.reason(decision(), chunk("D-99", "S1", "INTERNAL", "NONE")), v.RECORD_MISSING)
        self.assertEqual(self.reason(decision(), chunk(label=None)), v.ATTRIBUTES_MISSING)

    def test_invalid_current_record(self):
        broken = dict(RECORDS, **{"D-03": support.record(document_label="internal")})
        self.assertEqual(self.reason(decision(["BID-ORION"]), chunk(), broken), v.RECORD_INVALID)

    def test_one_mismatch_withholds_every_chunk(self):
        good = chunk("D-03", "S3", "INTERNAL", "NONE")
        result = v.verify(decision(), [good, chunk()], RECORDS)
        self.assertEqual((result.status, result.verified), (v.MISMATCH, ()))


class Relevance(unittest.TestCase):
    def test_threshold_and_order(self):
        low, high, mid = chunk(score=0.2, chunk_id="low"), chunk(score=0.9, chunk_id="high"), chunk(score=0.6, chunk_id="mid")
        kept, omitted = relevance.apply([low, high, mid], 0.5)
        self.assertEqual([c.chunk_id for c in kept], ["high", "mid"])
        self.assertEqual([c.chunk_id for c in omitted], ["low"])

    def test_relevance_cannot_see_the_requester(self):
        self.assertEqual(list(inspect.signature(relevance.apply).parameters), ["verified_chunks", "min_score"])

    def test_omitting_a_low_score_chunk_does_not_change_its_eligibility(self):
        d, low = decision(["BID-ORION"]), chunk(score=0.1)
        verified = v.verify(d, [low], RECORDS).verified
        kept, omitted = relevance.apply(verified, 0.5)
        self.assertEqual((kept, len(omitted)), ((), 1))
        self.assertTrue(e.is_eligible(d, low.label, low.scope))


class AuditRecord(unittest.TestCase):
    def base(self):
        record = audit_record.new("r-1", "tla-s01e02-normal", "normal")
        record.update(outcome="ANSWERED", retrieval=[audit_record.retrieval_entry(chunk())])
        return record

    def test_valid_record(self):
        audit_record.validate(self.base())

    def test_retrieval_entry_carries_no_text(self):
        self.assertNotIn("text", audit_record.retrieval_entry(chunk()))

    def test_question_answer_and_content_fields_are_rejected(self):
        for field in ("question", "question_sha256", "answer", "text", "token", "content"):
            record = self.base()
            record[field] = "x"
            with self.assertRaises(audit_record.AuditSchemaError):
                audit_record.validate(record)

    def test_nested_content_is_rejected(self):
        record = self.base()
        record["retrieval"][0]["text"] = "chunk text"
        with self.assertRaises(audit_record.AuditSchemaError):
            audit_record.validate(record)
        record = self.base()
        record["generation"] = {"invoked": True, "prompt": "p"}
        with self.assertRaises(audit_record.AuditSchemaError):
            audit_record.validate(record)

    def test_detail_is_a_short_code(self):
        record = self.base()
        record["detail"] = "x" * 200
        with self.assertRaises(audit_record.AuditSchemaError):
            audit_record.validate(record)


if __name__ == "__main__":
    unittest.main()
