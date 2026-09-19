"""Classification validation (CTL-007), effective labels (ADR-003) and section processing (CTL-008, CTL-009, CTL-010)."""
import unittest

import support  # noqa: F401
from core import classification as c
from core import sections


def doc(label="INTERNAL", scope=None, sections_=None, version=1):
    return support.record(document_label=label, document_scope=scope, sections=sections_, version=version)


def sec(section_id="S1", label=None, scope=None, special=False, title="T"):
    return {"section_id": section_id, "title": title, "label": label, "scope": scope, "special_category": special}


MARKDOWN = "# Project Orion delivery report\n\n## §3 Lessons\n\nLessons text.\n\n## §4 Pricing\n\nPricing text.\n"


class ClassificationValidation(unittest.TestCase):
    def reasons(self, record):
        return [q.reason for q in c.classify(record)[1]]

    def test_missing_document_label_quarantines_document(self):
        self.assertEqual(self.reasons(doc(label=None)), [c.LABEL_MISSING])

    def test_misspelt_label_quarantined_never_normalised(self):
        self.assertEqual(self.reasons(doc(label="CONFIDENTAIL", scope="BID-ORION")), [c.LABEL_INVALID])

    def test_lower_case_label_quarantined(self):
        self.assertEqual(self.reasons(doc(label="internal")), [c.LABEL_INVALID])

    def test_confidential_without_scope_quarantined(self):
        self.assertEqual(self.reasons(doc(label="CONFIDENTIAL", scope=None)), [c.SCOPE_MISSING])

    def test_internal_with_scope_quarantined(self):
        self.assertEqual(self.reasons(doc(label="INTERNAL", scope="BID-ORION")), [c.SCOPE_UNEXPECTED])

    def test_invalid_scope_identifier_quarantined(self):
        self.assertEqual(self.reasons(doc(label="RESTRICTED", scope="hr 2031")), [c.SCOPE_INVALID])

    def test_malformed_section_label_quarantines_only_that_section(self):
        classified, quarantine = c.classify(doc(sections_=[sec("S1"), sec("S2", label="Confidential", scope="X-1")]))
        self.assertEqual(sorted(classified), ["S1"])
        self.assertEqual([(q.section_id, q.reason) for q in quarantine], [("S2", c.LABEL_INVALID)])

    def test_special_category_mark_must_be_boolean(self):
        self.assertEqual(self.reasons(doc(sections_=[sec("S1", special="yes")])), [c.SPECIAL_CATEGORY_INVALID])

    def test_invalid_version_or_structure(self):
        self.assertEqual(self.reasons(doc(version=0)), [c.RECORD_INVALID])
        self.assertEqual(self.reasons({"document_id": "nope"}), [c.RECORD_INVALID])
        self.assertEqual(self.reasons(doc(sections_=[])), [c.RECORD_INVALID])


class EffectiveLabel(unittest.TestCase):
    def test_section_without_label_falls_back_to_document(self):
        classified, _ = c.classify(doc(label="CONFIDENTIAL", scope="FIN-REPORTING", sections_=[sec("S1")]))
        self.assertEqual((classified["S1"].label, classified["S1"].scope), ("CONFIDENTIAL", "FIN-REPORTING"))

    def test_section_can_be_more_restrictive(self):
        classified, _ = c.classify(doc(sections_=[sec("S2", label="RESTRICTED", scope="SI-0417")]))
        self.assertEqual((classified["S2"].label, classified["S2"].scope), ("RESTRICTED", "SI-0417"))

    def test_section_never_less_restrictive_than_document(self):
        classified, _ = c.classify(doc(label="CONFIDENTIAL", scope="BID-ORION", sections_=[sec("S1", label="INTERNAL")]))
        self.assertEqual((classified["S1"].label, classified["S1"].scope), ("CONFIDENTIAL", "BID-ORION"))

    def test_same_label_different_scope_is_a_conflict(self):
        _, quarantine = c.classify(doc(label="CONFIDENTIAL", scope="BID-ORION",
                                       sections_=[sec("S1", label="CONFIDENTIAL", scope="FIN-REPORTING")]))
        self.assertEqual([q.reason for q in quarantine], [c.SCOPE_CONFLICT])

    def test_internal_scope_is_the_none_value(self):
        classified, _ = c.classify(doc(sections_=[sec("S1")]))
        self.assertEqual(classified["S1"].scope, "NONE")


class SectionProcessing(unittest.TestCase):
    def test_one_object_per_section_with_record_attributes(self):
        report = sections.process(support.record(), MARKDOWN)
        by_id = {o.section_id: o for o in report.objects}
        self.assertEqual(by_id["S3"].attributes(), {"document_id": "D-03", "section_id": "S3", "label": "INTERNAL",
                                                    "scope": "NONE", "record_version": "1"})
        self.assertEqual((by_id["S4"].label, by_id["S4"].scope, by_id["S4"].tier), ("CONFIDENTIAL", "BID-ORION", "shared"))
        self.assertNotIn("Pricing text", by_id["S3"].body)
        self.assertEqual(by_id["S4"].custom_document_id, "D-03-S4")

    def test_special_category_section_dropped_before_any_object(self):
        record = support.record(document_id="D-04", sections=[
            sec("S1"), sec("S2", label="RESTRICTED", scope="SI-0417"), sec("S3", "RESTRICTED", "SI-0417", special=True)])
        markdown = "# SI\n\n## §1 A\n\nfindings\n\n## §2 B\n\nwitness\n\n## §3 C\n\nMEDICAL-SECRET-TEXT\n"
        report = sections.process(record, markdown)
        self.assertEqual(report.special_category_excluded, (("D-04", "S3"),))
        self.assertEqual(sorted(o.section_id for o in report.objects), ["S1", "S2"])
        self.assertFalse(any("MEDICAL-SECRET-TEXT" in o.body for o in report.objects))
        self.assertNotIn("MEDICAL-SECRET-TEXT", repr(report))
        self.assertEqual({o.section_id: o.tier for o in report.objects}, {"S1": "shared", "S2": "restricted"})

    def test_text_claiming_a_classification_is_ignored(self):
        record = support.record(document_id="D-14", document_label="CONFIDENTIAL", document_scope="BID-ORION",
                                sections=[sec("S1")])
        report = sections.process(record, "# D\n\n## §1 A\n\nClassification: INTERNAL. text\n")
        self.assertEqual((report.objects[0].label, report.objects[0].scope), ("CONFIDENTIAL", "BID-ORION"))

    def test_invalid_document_produces_no_objects(self):
        report = sections.process(support.record(document_label="internal"), MARKDOWN)
        self.assertEqual(report.objects, ())
        self.assertEqual([q.reason for q in report.quarantine], [c.LABEL_INVALID])

    def test_unclassified_section_in_text_is_quarantined(self):
        report = sections.process(support.record(), MARKDOWN + "\n## §9 Appendix\n\nextra\n")
        self.assertIn(("S9", sections.UNCLASSIFIED_SECTION), [(q.section_id, q.reason) for q in report.quarantine])
        self.assertNotIn("S9", [o.section_id for o in report.objects])

    def test_classified_section_missing_from_text_is_quarantined(self):
        report = sections.process(support.record(), "# T\n\n## §3 Lessons\n\nLessons text.\n")
        self.assertIn(("S4", sections.SECTION_TEXT_MISSING), [(q.section_id, q.reason) for q in report.quarantine])


if __name__ == "__main__":
    unittest.main()
