"""Before-generation verification (CTL-014, CTL-030, CTL-031; Episode 02 ADR-005, Episode 03 ADR-001 and ADR-002).

Every retrieved chunk is checked again against the CURRENT authoritative record and against THIS request's decision.
If ANY chunk fails, the whole answer is withheld and the model is not invoked.

Episode 02 compared label, scope and version. Episode 03 adds the rest of the authoritative state and the convergence
view, in one place, so a chunk is judged once:

    authority says the document is superseded, withdrawn or deleted   → NOT_CURRENT
    a change is known and derived state has not caught up             → PENDING_CHANGE
    the state cannot be established at all                            → UNKNOWN_STATE

    KNOWN STALE IS NOT CURRENT: when a newer version is effective but not yet retrievable, the previous
    version is withheld, never presented with a notice.

This is still verification, detection and containment. It is NOT a substitute for the mandatory pre-retrieval
constraint: when it fires, ineligible or stale content has already crossed the retrieval boundary into memory.
"""
from dataclasses import dataclass

from core import classification, convergence, record_state
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
# Episode 03
NOT_CURRENT = "NOT_CURRENT"
PENDING_CHANGE = "PENDING_CHANGE"
UNKNOWN_STATE = "UNKNOWN_STATE"

CURRENCY_REASONS = (NOT_CURRENT, PENDING_CHANGE, UNKNOWN_STATE)


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
    states: dict = None         # document_id → convergence state, for the audit record

    @property
    def currency_reasons(self):
        return tuple(r for _, r in self.mismatches if r in CURRENCY_REASONS)


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


def currency_reason(state):
    """The mismatch reason for a convergence state, or None when the document may be served."""
    if state == convergence.KNOWN_CURRENT:
        return None
    if state == convergence.KNOWN_GONE:
        return NOT_CURRENT
    if state == convergence.KNOWN_PENDING:
        return PENDING_CHANGE
    return UNKNOWN_STATE


def check_chunk(decision, chunk, sections, invalid, states=None):
    """Return None if the chunk passes, otherwise the first failing reason.

    The currency check runs FIRST: a superseded document must fail as NOT_CURRENT even when its label, scope and
    version still match — which is precisely the case Episode 02's checks let through.
    """
    if states is not None:
        reason = currency_reason(states.get(chunk.document_id, convergence.UNKNOWN))
        if reason:
            return reason
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


def verify(decision, chunks, records, view=None, now=None):
    """`records` is {document_id: current authoritative record or None} read from the records store.

    `view` is a core.convergence.ConvergenceView. When it is omitted the currency checks are skipped — that is the
    Episode 02 behaviour, kept only for the unit tests of the older rules.
    """
    sections, invalid = current_sections(records)
    states = None
    if view is not None:
        record_states = record_state.states(records)
        states = {document_id: convergence.classify(document_id, state, view, now)
                  for document_id, state in record_states.items()}
    mismatches = []
    for chunk in chunks:
        reason = check_chunk(decision, chunk, sections, invalid, states)
        if reason:
            mismatches.append((chunk.chunk_id, reason))
    if mismatches or not chunks:
        return VerificationResult(MISMATCH if mismatches else PASS, (), tuple(mismatches), states)
    return VerificationResult(PASS, tuple(chunks), (), states)
