"""Outcome codes and the control that stops each request (Episode 02's table, extended for Episode 03).

One table, so the audit record, the uniform response and the tests agree on what happened and which control decided it.
The response a person sees never distinguishes these outcomes; only the content-free audit record does.

Episode 03 adds the outcomes of convergence-aware serving. They are withholdings, not errors: the system is refusing to
present content it cannot confirm is current (ADR-002).

Episode 03 controls:
    CTL-030  authoritative request-time status confirmation      (ADR-001, ADR-002)
    CTL-031  convergence gate: pending / unknown is not served   (ADR-002)
    CTL-032  monotonic, idempotent change application            (ADR-004)
    CTL-033  generation build, verify, switch, retire            (ADR-005)
    CTL-034  deletion across the derived-copy graph              (ADR-006)
    CTL-035  reconciliation and watermark advancement            (ADR-003)
    CTL-036  freshness evidence                                  (ADR-007)
"""

ANSWERED = "ANSWERED"
REFUSED_INVALID_REQUEST = "REFUSED_INVALID_REQUEST"
REFUSED_AUTHORIZATION_UNAVAILABLE = "REFUSED_AUTHORIZATION_UNAVAILABLE"
REFUSED_NO_ACTIVE_EMPLOYMENT = "REFUSED_NO_ACTIVE_EMPLOYMENT"
REFUSED_CONSTRAINT_INCOMPLETE = "REFUSED_CONSTRAINT_INCOMPLETE"
RETRIEVAL_ERROR = "RETRIEVAL_ERROR"
NO_ELIGIBLE_CONTENT = "NO_ELIGIBLE_CONTENT"
WITHHELD_VERIFICATION_MISMATCH = "WITHHELD_VERIFICATION_MISMATCH"
WITHHELD_CLASSIFICATION_UNAVAILABLE = "WITHHELD_CLASSIFICATION_UNAVAILABLE"
NO_RELEVANT_CONTENT = "NO_RELEVANT_CONTENT"
GENERATION_ERROR = "GENERATION_ERROR"
INTERNAL_ERROR = "INTERNAL_ERROR"

# ── Episode 03 ──────────────────────────────────────────────────────────────────────────────────────────────────────
WITHHELD_NOT_CURRENT = "WITHHELD_NOT_CURRENT"          # authority says superseded, withdrawn or deleted
WITHHELD_PENDING_CHANGE = "WITHHELD_PENDING_CHANGE"    # a newer effective version is not yet retrievable
WITHHELD_UNKNOWN_STATE = "WITHHELD_UNKNOWN_STATE"      # the state could not be established at all
WITHHELD_CONVERGENCE_UNAVAILABLE = "WITHHELD_CONVERGENCE_UNAVAILABLE"   # convergence store unreadable (fail closed)

FAILING_CONTROL = {
    ANSWERED: None,
    REFUSED_INVALID_REQUEST: None,
    REFUSED_AUTHORIZATION_UNAVAILABLE: "CTL-004",
    REFUSED_NO_ACTIVE_EMPLOYMENT: "CTL-004",
    REFUSED_CONSTRAINT_INCOMPLETE: "CTL-013",
    RETRIEVAL_ERROR: "CTL-013",
    NO_ELIGIBLE_CONTENT: None,             # not a failure: nothing the requester may see matched
    WITHHELD_VERIFICATION_MISMATCH: "CTL-014",
    WITHHELD_CLASSIFICATION_UNAVAILABLE: "CTL-014",
    NO_RELEVANT_CONTENT: None,             # answer quality, never authorization
    GENERATION_ERROR: None,
    INTERNAL_ERROR: None,
    WITHHELD_NOT_CURRENT: "CTL-030",
    WITHHELD_PENDING_CHANGE: "CTL-031",
    WITHHELD_UNKNOWN_STATE: "CTL-031",
    WITHHELD_CONVERGENCE_UNAVAILABLE: "CTL-031",
}

# Outcomes in which the knowledge bases must not have been searched at all (ADR-002 of Episode 02: no authoritative
# current grants = no retrieval).
NO_RETRIEVAL_OUTCOMES = frozenset({REFUSED_INVALID_REQUEST, REFUSED_AUTHORIZATION_UNAVAILABLE,
                                   REFUSED_NO_ACTIVE_EMPLOYMENT, REFUSED_CONSTRAINT_INCOMPLETE})

# Outcomes in which the model must not have been invoked.
NO_GENERATION_OUTCOMES = frozenset(set(FAILING_CONTROL) - {ANSWERED, GENERATION_ERROR})

# Episode 03 withholdings: the answer was stopped because derived state could not be confirmed current.
NOT_CURRENT_OUTCOMES = frozenset({WITHHELD_NOT_CURRENT, WITHHELD_PENDING_CHANGE, WITHHELD_UNKNOWN_STATE,
                                  WITHHELD_CONVERGENCE_UNAVAILABLE})


class Refusal(Exception):
    """Stops the request. `detail` is a short, content-free reason (an error class or code), never text or data."""

    def __init__(self, outcome, detail=""):
        if outcome not in FAILING_CONTROL or outcome == ANSWERED:
            raise ValueError(f"unknown refusal outcome {outcome!r}")
        super().__init__(outcome)
        self.outcome = outcome
        self.detail = str(detail)[:120]

    @property
    def failing_control(self):
        return FAILING_CONTROL[self.outcome]
