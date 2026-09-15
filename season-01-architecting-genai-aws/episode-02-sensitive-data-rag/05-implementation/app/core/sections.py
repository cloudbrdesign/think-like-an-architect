"""Section processing: splitting, special-category exclusion and section objects (CTL-008, CTL-009, CTL-010).

  * One document is split at `## §<n> <title>` headings into sections S<n>.
  * SPECIAL-CATEGORY SECTIONS ARE DROPPED HERE — before any object write, knowledge-base ingestion or embedding. Their
    text never leaves this function; the report carries only identifiers and a count.
  * Every other section becomes ONE object carrying the section's effective label and scope from the classification
    record (never from text), its document, section and record version, and the tier its label belongs to. One object
    per section means the service can split a long section into several chunks, but a chunk can never span sections
    and every chunk keeps these attributes (SPK-E02-A C1).
  * A section present in the text but absent from the record (or the reverse) is quarantined.
"""
import re
from dataclasses import dataclass

from core import classification
from core.tier_selection import tier_for_label

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
        """Inline attributes written at ingestion; every chunk of this object carries them."""
        return {"document_id": self.document_id, "section_id": self.section_id, "label": self.label,
                "scope": self.scope, "record_version": str(self.record_version)}


@dataclass(frozen=True)
class ProcessingReport:
    objects: tuple
    quarantine: tuple
    special_category_excluded: tuple     # (document_id, section_id) only — never text


def split(markdown):
    """Return {section_id: body}. Text before the first heading (the title) is not a section and is never indexed."""
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
    bodies = split(markdown)
    objects, special = [], []
    for section_id in sorted(set(bodies) - set(classified) - {q.section_id for q in quarantine}):
        quarantine.append(classification.Quarantine(document_id, section_id, UNCLASSIFIED_SECTION))
    for section_id, section in sorted(classified.items()):
        if section.special_category:
            special.append((document_id, section_id))                  # excluded before anything is written
            continue
        if section_id not in bodies or not bodies[section_id]:
            quarantine.append(classification.Quarantine(document_id, section_id, SECTION_TEXT_MISSING))
            continue
        body = f"{section.document_title} — {section.section_title}\n\n{bodies[section_id]}"
        objects.append(SectionObject(document_id, section_id, tier_for_label(section.label), section.label,
                                     section.scope, section.version, body))
    return ProcessingReport(tuple(objects), tuple(quarantine), tuple(special))
