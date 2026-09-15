"""Outcome codes and the control that stops each request (IMPLEMENTATION_DESIGN §5.7).

One table, so the audit record, the uniform response and the tests agree on what happened and which control decided it.
The response a person sees never distinguishes these outcomes; only the content-free audit record does.
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
    NO_RELEVANT_CONTENT: None,             # answer quality, never authorization (IMPLEMENTATION_DESIGN §5.5)
    GENERATION_ERROR: None,
    INTERNAL_ERROR: None,
}

# Outcomes in which the knowledge bases must not have been searched at all (ADR-002: no authoritative current
# grants = no retrieval).
NO_RETRIEVAL_OUTCOMES = frozenset({REFUSED_INVALID_REQUEST, REFUSED_AUTHORIZATION_UNAVAILABLE,
                                   REFUSED_NO_ACTIVE_EMPLOYMENT, REFUSED_CONSTRAINT_INCOMPLETE})

# Outcomes in which the model must not have been invoked.
NO_GENERATION_OUTCOMES = frozenset(set(FAILING_CONTROL) - {ANSWERED, GENERATION_ERROR})


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
