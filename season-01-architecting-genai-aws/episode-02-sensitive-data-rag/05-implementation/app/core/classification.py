"""Classification records: validation (CTL-007) and the effective label of a section (ADR-003).

The records system's classification record is the ONLY source of a section's label, scope, version and special-category
mark (CTL-006). Text inside a document never classifies it. Anything that is not exactly valid is quarantined — never
normalised, guessed or defaulted to a less restrictive label.

Record shape (fixtures/classification_records.json):
    {document_id, title, document_label, document_scope, version,
     sections: [{section_id, title, label, scope, special_category}]}
A section whose label is null inherits the document's label and scope (document fallback). A section can make itself
more restrictive than its document, never less.
"""
import re
from dataclasses import dataclass

from core.eligibility import LABELS, NO_SCOPE, RESTRICTIVENESS, INTERNAL, valid_scope_id

DOCUMENT_ID = re.compile(r"^D-\d{2}$")
SECTION_ID = re.compile(r"^S\d{1,3}$")

# Quarantine reason codes (content-free; used in the quarantine report)
LABEL_MISSING = "LABEL_MISSING"
LABEL_INVALID = "LABEL_INVALID"                  # misspelt, wrong case or any non-canonical value
SCOPE_MISSING = "SCOPE_MISSING"
SCOPE_INVALID = "SCOPE_INVALID"
SCOPE_UNEXPECTED = "SCOPE_UNEXPECTED"            # INTERNAL with a scope
SCOPE_CONFLICT = "SCOPE_CONFLICT"                # same label as the document, different scope
RECORD_INVALID = "RECORD_INVALID"
SPECIAL_CATEGORY_INVALID = "SPECIAL_CATEGORY_INVALID"


@dataclass(frozen=True)
class SectionClassification:
    document_id: str
    section_id: str
    label: str              # effective label
    scope: str              # effective scope (NO_SCOPE for INTERNAL)
    special_category: bool
    version: int
    document_title: str
    section_title: str


@dataclass(frozen=True)
class Quarantine:
    document_id: str
    section_id: object      # None when the whole document is quarantined
    reason: str


def _label_problem(label, scope):
    if label is None:
        return LABEL_MISSING
    if label not in LABELS:
        return LABEL_INVALID
    if label == INTERNAL:
        return SCOPE_UNEXPECTED if scope not in (None, NO_SCOPE) else None
    if scope is None or scope == "":
        return SCOPE_MISSING
    return None if valid_scope_id(scope) else SCOPE_INVALID


def _scope(label, scope):
    return NO_SCOPE if label == INTERNAL else scope


def effective(document_label, document_scope, section_label, section_scope):
    """Return (label, scope) or raise ValueError(reason). Inputs must already be valid."""
    doc = (document_label, _scope(document_label, document_scope))
    if section_label is None:
        return doc
    sec = (section_label, _scope(section_label, section_scope))
    if RESTRICTIVENESS[sec[0]] > RESTRICTIVENESS[doc[0]]:
        return sec
    if RESTRICTIVENESS[sec[0]] < RESTRICTIVENESS[doc[0]]:
        return doc                                        # never less restrictive than the document
    if sec[1] != doc[1]:
        raise ValueError(SCOPE_CONFLICT)
    return sec


def classify(record):
    """Validate one document's record. Returns (sections: dict section_id -> SectionClassification, quarantine: list).

    A document-level problem quarantines the whole document; a section-level problem quarantines that section only.
    """
    if not isinstance(record, dict) or not DOCUMENT_ID.match(str(record.get("document_id", ""))):
        return {}, [Quarantine(str((record or {}).get("document_id")) if isinstance(record, dict) else "?", None,
                               RECORD_INVALID)]
    document_id = record["document_id"]
    version = record.get("version")
    sections = record.get("sections")
    if (not isinstance(version, int) or isinstance(version, bool) or version < 1 or not isinstance(sections, list)
            or not sections or not isinstance(record.get("title"), str)):
        return {}, [Quarantine(document_id, None, RECORD_INVALID)]
    problem = _label_problem(record.get("document_label"), record.get("document_scope"))
    if problem:
        return {}, [Quarantine(document_id, None, problem)]
    result, quarantine, seen = {}, [], set()
    for section in sections:
        section_id = section.get("section_id") if isinstance(section, dict) else None
        if not isinstance(section_id, str) or not SECTION_ID.match(section_id) or section_id in seen \
                or not isinstance(section.get("title"), str):
            quarantine.append(Quarantine(document_id, section_id if isinstance(section_id, str) else None,
                                         RECORD_INVALID))
            continue
        seen.add(section_id)
        special = section.get("special_category")
        if not isinstance(special, bool):
            quarantine.append(Quarantine(document_id, section_id, SPECIAL_CATEGORY_INVALID))
            continue
        label, scope = section.get("label"), section.get("scope")
        if label is not None:
            problem = _label_problem(label, scope)
            if problem:
                quarantine.append(Quarantine(document_id, section_id, problem))
                continue
        try:
            eff_label, eff_scope = effective(record["document_label"], record.get("document_scope"), label, scope)
        except ValueError as error:
            quarantine.append(Quarantine(document_id, section_id, str(error)))
            continue
        result[section_id] = SectionClassification(document_id, section_id, eff_label, eff_scope, special, version,
                                                   record["title"], section["title"])
    return result, quarantine
