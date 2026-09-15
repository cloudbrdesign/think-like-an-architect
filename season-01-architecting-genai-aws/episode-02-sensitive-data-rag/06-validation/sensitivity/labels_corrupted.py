"""SENSITIVITY VARIANT — TEST ONLY — experiment 2 (TST-SEN-002). Never part of the normal build.

Replaces core/sections.py in its own throwaway deployment. Label PROPAGATION is corrupted: every section inherits its
DOCUMENT's label and scope, ignoring the section marks in the classification record, and is routed by that corrupted
label. So D-03 §4 (CONFIDENTIAL BID-ORION) is indexed as INTERNAL, and D-04 §2 (RESTRICTED SI-0417) is indexed as
INTERNAL in the SHARED tier.

Unchanged on purpose: classification validation, quarantine, and special-category exclusion (special-category data is
never indexed, in any deployment). Verification still compares chunks with the authoritative record.
"""
import re
from dataclasses import dataclass

from core import classification
from core.eligibility import INTERNAL, NO_SCOPE
from core.tier_selection import tier_for_label

VARIANT_MARKER = "SENSITIVITY VARIANT"
HEADING = re.compile(r"^## §(\d{1,3}) (.+)$", re.MULTILINE)
UNCLASSIFIED_SECTION = "UNCLASSIFIED_SECTION"
SECTION_TEXT_MISSING = "SECTION_TEXT_MISSING"


@dataclass(frozen=True)
class SectionObject:
    document_id: str
    section_id: str
    tier: str
    label: str
    scope: str
    record_version: int
    body: str

    @property
    def custom_document_id(self):
        return f"{self.document_id}-{self.section_id}"

    @property
    def object_key(self):
        return f"sections/{self.document_id}/{self.section_id}.txt"

    def attributes(self):
        return {"document_id": self.document_id, "section_id": self.section_id, "label": self.label,
                "scope": self.scope, "record_version": str(self.record_version)}


@dataclass(frozen=True)
class ProcessingReport:
    objects: tuple
    quarantine: tuple
    special_category_excluded: tuple


def split(markdown):
    matches = list(HEADING.finditer(markdown))
    result = {}
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(markdown)
        result[f"S{match.group(1)}"] = markdown[match.end():end].strip()
    return result


def process(record, markdown):
    classified, quarantine = classification.classify(record)
    quarantine = list(quarantine)
    if any(q.section_id is None for q in quarantine):
        return ProcessingReport((), tuple(quarantine), ())
    document_id = record["document_id"]
    # FAULT: the document's label and scope are applied to every section.
    doc_label = record["document_label"]
    doc_scope = NO_SCOPE if doc_label == INTERNAL else record["document_scope"]
    bodies = split(markdown)
    objects, special = [], []
    for section_id, section in sorted(classified.items()):
        if section.special_category:
            special.append((document_id, section_id))
            continue
        if section_id not in bodies or not bodies[section_id]:
            quarantine.append(classification.Quarantine(document_id, section_id, SECTION_TEXT_MISSING))
            continue
        body = f"{section.document_title} — {section.section_title}\n\n{bodies[section_id]}"
        objects.append(SectionObject(document_id, section_id, tier_for_label(doc_label), doc_label, doc_scope,
                                     section.version, body))
    return ProcessingReport(tuple(objects), tuple(quarantine), tuple(special))
