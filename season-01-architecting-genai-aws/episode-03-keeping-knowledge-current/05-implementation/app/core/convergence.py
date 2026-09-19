"""Convergence state: what the system knows about each document, and what it has proven (CTL-031; ADR-002, ADR-003).

    UNKNOWN DERIVED STATE IS NOT TRUSTED.

Every retrieval candidate is in exactly one of four states, and staleness is never reduced to an age number:

    KNOWN_CURRENT      authority says this version is in force, and derived state matches it   → may be served
    KNOWN_PENDING      a change is known and derived state has not caught up                   → never served as current
    KNOWN_GONE         superseded, withdrawn or deleted in the authoritative record            → never served
    UNKNOWN            the system cannot establish the state                                   → never served

The watermark is the second half of the picture. Its semantics are exact (ADR-007):

    "For this change class, every authoritative change effective at or before T has been applied to derived state or is
     listed as pending."

It is a statement about completeness of knowledge, not about processing progress. Only a completed reconciliation pass
may advance it (ADR-003); a notification never does, because a change that was never delivered is invisible to delivery.
"""
from dataclasses import dataclass, field

KNOWN_CURRENT = "KNOWN_CURRENT"
KNOWN_PENDING = "KNOWN_PENDING"
KNOWN_GONE = "KNOWN_SUPERSEDED_WITHDRAWN_DELETED"
UNKNOWN = "UNKNOWN"
STATES = (KNOWN_CURRENT, KNOWN_PENDING, KNOWN_GONE, UNKNOWN)
SERVABLE_STATES = frozenset({KNOWN_CURRENT})

# Change classes. Each has its own watermark and its own freshness window (FRS-001); the global floor is the
# conservative minimum across them, so a class that is behind is never hidden by a class that is current.
SUPERSEDE_WITHDRAW = "supersede_withdraw"
RECLASSIFY_UP = "reclassify_up"
RECLASSIFY_DOWN = "reclassify_down"
NEW_VERSION = "new_version"
DELETION = "deletion"
CHANGE_CLASSES = (SUPERSEDE_WITHDRAW, RECLASSIFY_UP, NEW_VERSION, RECLASSIFY_DOWN, DELETION)
SAFETY_CRITICAL_CLASSES = frozenset({SUPERSEDE_WITHDRAW, RECLASSIFY_UP, DELETION})


@dataclass(frozen=True)
class Pending:
    """A change known to be effective in the record and not yet reflected in derived state."""
    document_id: str
    change_class: str
    effective_version: int
    noticed_at: str
    detail: object = None                 # content-free: the reason code that created the entry
    # Retry and escalation accounting (FRS-004, OPS-001). Written by the change path only; the request path reads
    # `noticed_at` and never these.
    attempts: int = 0                     # genuine repair invocations that did NOT converge, never observations
    last_attempt_at: object = None
    escalated_at: object = None           # set once, when this change outlived its class's window (ADR-007 §3)

    def item(self):
        """The AUDIT projection: exactly the fields `audit_record.PENDING` allows, and nothing more.

        The request path puts this straight into the content-free audit record, which validates every entry against
        an allow-list. Retry and escalation accounting is change-path state that no frozen requirement places in the
        request-path record, so it is deliberately NOT here: adding it would make every request that has a pending
        document fail schema validation. What the table keeps is `stored()`.
        """
        return {"document_id": self.document_id, "change_class": self.change_class,
                "effective_version": self.effective_version, "noticed_at": self.noticed_at, "detail": self.detail}

    def stored(self):
        """The PERSISTENCE projection: everything the convergence table keeps for this entry."""
        return {**self.item(), "attempts": int(self.attempts), "last_attempt_at": self.last_attempt_at,
                "escalated_at": self.escalated_at}


@dataclass(frozen=True)
class Watermark:
    """What reconciliation has proven for one change class."""
    change_class: str
    proven_through: object = None         # ISO-8601, or None when nothing has been proven yet
    reconciliation_run_id: object = None
    completed_at: object = None
    documents_compared: int = 0

    @property
    def proven(self):
        return self.proven_through is not None

    def item(self):
        return {"change_class": self.change_class, "proven_through": self.proven_through,
                "reconciliation_run_id": self.reconciliation_run_id, "completed_at": self.completed_at,
                "documents_compared": self.documents_compared}


@dataclass(frozen=True)
class ConvergenceView:
    """What the request path was able to establish for one request."""
    pending: dict = field(default_factory=dict)          # document_id → Pending
    watermarks: dict = field(default_factory=dict)       # change_class → Watermark
    available: bool = True                               # False when the convergence store could not be read

    def pending_for(self, document_id):
        return self.pending.get(document_id)


def classify(document_id, record_state, view, now=None):
    """The candidate's state. `record_state` is a core.record_state.RecordState; `view` a ConvergenceView.

    Order matters, and it is the order of trust:
      1 the convergence store could not be read      → UNKNOWN (we cannot say what we do not know)
      2 the authoritative record is invalid          → UNKNOWN
      3 authority says the document is not in force  → KNOWN_GONE
      4 a change is pending for it                   → KNOWN_PENDING
      5 otherwise                                    → KNOWN_CURRENT

    A status change dated in the future has not happened yet: the document stays servable until its `effective_from`
    arrives (core.record_state.is_effective).
    """
    from core.record_state import is_effective
    if not view.available:
        return UNKNOWN
    if record_state is None or not record_state.valid:
        return UNKNOWN
    if not record_state.servable:
        return KNOWN_GONE if is_effective(record_state, now) else KNOWN_CURRENT
    if view.pending_for(document_id) is not None:
        return KNOWN_PENDING
    return KNOWN_CURRENT


def servable(state):
    return state in SERVABLE_STATES


def global_floor(watermarks):
    """The conservative minimum across classes: the strongest statement the system as a whole may make.

    A class that has never been proven makes the floor unproven, whatever the other classes say.
    """
    if not watermarks:
        return None
    proven = [w.proven_through for w in watermarks.values()]
    if any(p is None for p in proven):
        return None
    return min(proven)


def limiting_class(watermarks):
    """Which change class is holding the global floor back (evidence question, ADR-007)."""
    if not watermarks:
        return None
    unproven = sorted(c for c, w in watermarks.items() if not w.proven)
    if unproven:
        return unproven[0]
    return min(watermarks.items(), key=lambda item: item[1].proven_through)[0]


def change_class_for(before, after, before_label=None, after_label=None):
    """Classify a change from two RecordStates (either may be None) and, when known, the document labels.

    A change that is several things at once is reported as the most consequential: gone beats reclassification, and
    reclassification beats a new version.
    """
    from core.record_state import DELETED, SUPERSEDED, WITHDRAWN
    if after is None or after.status == DELETED:
        return DELETION
    if after.status in (SUPERSEDED, WITHDRAWN):
        return SUPERSEDE_WITHDRAW
    reclassification = reclassification_class(before_label, after_label)
    if reclassification is not None:
        return reclassification
    return NEW_VERSION


def reclassification_class(before_label, after_label):
    """Upward or downward reclassification, by restrictiveness (the safety-critical direction is upward)."""
    from core.eligibility import RESTRICTIVENESS
    before, after = RESTRICTIVENESS.get(before_label), RESTRICTIVENESS.get(after_label)
    if before is None or after is None or before == after:
        return None
    return RECLASSIFY_UP if after > before else RECLASSIFY_DOWN
