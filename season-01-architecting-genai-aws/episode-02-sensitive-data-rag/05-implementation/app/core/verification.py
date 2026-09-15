"""Before-generation verification (CTL-014; ADR-005).

Every retrieved chunk is checked again against the CURRENT classification record and against THIS request's decision.
If ANY chunk fails, the whole answer is withheld and the model is not invoked.

This is verification, detection and containment. It is NOT a substitute for the mandatory pre-retrieval constraint:
when it fires, ineligible content has already crossed the retrieval boundary into the query function's memory.
"""
from dataclasses import dataclass

from core import classification
from core.eligibility import is_eligible
from core.tier_selection import TIER_FOR_LABEL

PASS, MISMATCH = "PASS", "MISMATCH"

# Mismatch reasons (content-free)
ATTRIBUTES_MISSING = "ATTRIBUTES_MISSING"
RECORD_MISSING = "RECORD_MISSING"
RECORD_INVALID = "RECORD_INVALID"
SPECIAL_CATEGORY = "SPECIAL_CATEGORY"
LABEL_MISMATCH = "LABEL_MISMATCH"
SCOPE_MISMATCH = "SCOPE_MISMATCH"
VERSION_MISMATCH = "VERSION_MISMATCH"
WRONG_TIER = "WRONG_TIER"
NOT_ELIGIBLE = "NOT_ELIGIBLE"


@dataclass(frozen=True)
class RetrievedChunk:
    chunk_id: str
    tier: str
    document_id: object
    section_id: object
    label: object
    scope: object
    record_version: object      # string attribute as indexed
    score: float
    text: str                   # held in memory for generation only; never audited or logged


@dataclass(frozen=True)
class VerificationResult:
    status: str
    verified: tuple
    mismatches: tuple           # ((chunk_id, reason), ...)


def current_sections(records):
    """{document_id: record-or-None} → ({(document_id, section_id): SectionClassification}, {document_id: problem})."""
    sections, invalid = {}, {}
    for document_id, record in records.items():
        if record is None:
            continue
        classified, quarantine = classification.classify(record)
        if any(q.section_id is None for q in quarantine):
            invalid[document_id] = RECORD_INVALID
        for section_id, section in classified.items():
            sections[(document_id, section_id)] = section
    return sections, invalid


def check_chunk(decision, chunk, sections, invalid):
    """Return None if the chunk passes, otherwise the first failing reason."""
    if not all(isinstance(v, str) and v for v in (chunk.document_id, chunk.section_id, chunk.label, chunk.scope,
                                                   chunk.record_version)):
        return ATTRIBUTES_MISSING
    if chunk.document_id in invalid:
        return RECORD_INVALID
    current = sections.get((chunk.document_id, chunk.section_id))
    if current is None:
        return RECORD_MISSING
    if current.special_category:
        return SPECIAL_CATEGORY
    if chunk.label != current.label:
        return LABEL_MISMATCH
    if chunk.scope != current.scope:
        return SCOPE_MISMATCH
    if chunk.record_version != str(current.version):
        return VERSION_MISMATCH
    if TIER_FOR_LABEL.get(current.label) != chunk.tier:
        return WRONG_TIER
    if not is_eligible(decision, current.label, current.scope):
        return NOT_ELIGIBLE
    return None


def verify(decision, chunks, records):
    """`records` is {document_id: current classification record or None} read from the classification store."""
    sections, invalid = current_sections(records)
    mismatches = []
    for chunk in chunks:
        reason = check_chunk(decision, chunk, sections, invalid)
        if reason:
            mismatches.append((chunk.chunk_id, reason))
    if mismatches or not chunks:
        return VerificationResult(MISMATCH if mismatches else PASS, (), tuple(mismatches))
    return VerificationResult(PASS, tuple(chunks), ())
