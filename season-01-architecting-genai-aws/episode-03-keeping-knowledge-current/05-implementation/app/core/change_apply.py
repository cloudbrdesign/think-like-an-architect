"""Monotonic, idempotent application of authoritative change (CTL-032; ADR-004).

    LATE, DUPLICATE AND REPLAYED CHANGES MUST NEVER REINSTATE OLDER AUTHORITATIVE STATE.

Retries, replays and reconciliation repairs all deliver the same change more than once, and notifications may arrive out
of order. So the decision to apply is made from the AUTHORITATIVE version — never arrival time, never a pipeline
sequence number:

    incoming.version >  reflected.version   → APPLY
    incoming.version == reflected.version   → DUPLICATE   (a no-op; safe to repeat)
    incoming.version <  reflected.version   → OLDER       (recorded as rejected, never silently dropped)
    reflected is DELETED                    → AFTER_DELETE (terminal for the record's lifetime)

An older arrival being visibly rejected is the point: FX-2 removes this rule and the older state returns.
"""
from dataclasses import dataclass

from core.record_state import DELETED

# A derived-state status, not an authoritative one: the record was read, and the decision was to index nothing from it
# (invalid classification, or every section special category). It is terminal for that version — never "not yet done".
QUARANTINED = "QUARANTINED"

APPLY = "APPLY"
DUPLICATE = "DUPLICATE"
OLDER = "OLDER"
AFTER_DELETE = "AFTER_DELETE"
DECISIONS = (APPLY, DUPLICATE, OLDER, AFTER_DELETE)


@dataclass(frozen=True)
class Reflected:
    """What derived state currently reflects for one document."""
    document_id: str
    version: int = 0
    status: object = None
    generation_id: object = None

    @property
    def deleted(self):
        return self.status == DELETED


def decide(reflected, incoming_version, incoming_status=None):
    """Return one of DECISIONS. `reflected` may be None when derived state holds nothing for the document."""
    if not isinstance(incoming_version, int) or isinstance(incoming_version, bool) or incoming_version < 1:
        raise ValueError("incoming version must be a positive integer from the authoritative record")
    if reflected is None:
        return APPLY
    if reflected.deleted and incoming_status != DELETED:
        # ADR-004 clause 4 has two halves: a deleted document cannot be reinstated by a LATE change, and "only a new
        # authoritative record can bring content back". A NEWER authoritative version is that new record — not a
        # replay — so it applies. Refusing it would leave authority and derived state permanently disagreeing, with
        # reconciliation requesting a repair for ever that can never succeed (FRS-007), while FRS-005 only ever
        # required that a late, duplicate or replayed change must not reinstate.
        return APPLY if incoming_version > reflected.version else AFTER_DELETE
    if incoming_version > reflected.version:
        return APPLY
    if incoming_version == reflected.version:
        # A record may change STATUS without a new version — supersession in place is the ordinary case, because
        # superseding a document does not edit it. Calling that a duplicate would leave the document pending for ever
        # while its derived copies went on serving, so the status is part of the decision. The status always comes
        # from a fresh authoritative read, never from the event payload, so this cannot replay an old status.
        return APPLY if incoming_status is not None and incoming_status != reflected.status else DUPLICATE
    return OLDER


def may_promote(reflected, candidate_version, candidate_status=None):
    """Whether a verified generation may REPLACE what is currently serving (AB-14).

    Monotonicity is an invariant over TRANSITIONS OF DERIVED STATE, not a feature of the incremental applier. The
    incremental apply, reconciliation repair, operator repair and rebuild all promote generations, and a path that
    reaches the switch without passing this check can move a document backwards — which is what rebuild did.

    The decision is the one `decide()` already makes, so monotonicity has exactly ONE definition:

        APPLY      the candidate is newer, or a status change at the same version   → promote
        DUPLICATE  the same version and status                                      → promote (rebuild is idempotent)
        OLDER      the candidate is behind what is serving                          → REFUSE
        AFTER_DELETE   a deleted document, and the candidate is not newer           → REFUSE

    Evaluate it at SWITCH time against a fresh read, never at the start of a build: a build takes seconds to minutes,
    and another path may have promoted a newer generation in between (the ADR-005 / AB-11 lesson, applied to
    promotion rather than to retirement).
    """
    return decide(reflected, candidate_version, candidate_status) in (APPLY, DUPLICATE)


def rejection(document_id, decision, reflected_version, incoming_version):
    """A content-free record of a change that was deliberately not applied (evidence for VT-3 and FX-2)."""
    return {"document_id": document_id, "decision": decision, "reflected_version": reflected_version,
            "incoming_version": incoming_version}
