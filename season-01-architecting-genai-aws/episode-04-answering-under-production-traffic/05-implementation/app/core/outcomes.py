"""The four caller-visible outcomes, and the only constructor that may produce them (CTL-404).

These are never collapsed. Counted separately, alerted separately, rendered differently. Merging CAPACITY_REFUSED with
TRUST_WITHHELD is the single most likely implementation defect and the reason TST-404 exists:

    CAPACITY_REFUSED  "I cannot serve this request now."   — a statement about us
    TRUST_WITHHELD    "I must not answer this request."     — a statement about the request

There is deliberately no default branch and no generic error outcome. An unrecognised outcome is a programming error,
raised, not silently rendered as one of the four.
"""
ANSWERED = "ANSWERED"
DEGRADED_BUT_ANSWERED = "DEGRADED_BUT_ANSWERED"
CAPACITY_REFUSED = "CAPACITY_REFUSED"
TRUST_WITHHELD = "TRUST_WITHHELD"

ALL = (ANSWERED, DEGRADED_BUT_ANSWERED, CAPACITY_REFUSED, TRUST_WITHHELD)


class Response:
    """A caller-visible response. Built only by the constructors below."""

    __slots__ = ("outcome", "body", "citations", "reduced", "degradation_level", "reason", "retry_after_seconds")

    def __init__(self, outcome, body=None, citations=None, reduced=None, degradation_level=0, reason=None,
                 retry_after_seconds=None):
        if outcome not in ALL:
            raise ValueError(f"unknown outcome {outcome!r}: the four outcomes are fixed by ADR-001")
        self.outcome = outcome
        self.body = body
        self.citations = tuple(citations or ())
        self.reduced = tuple(reduced or ())
        self.degradation_level = degradation_level
        self.reason = reason
        self.retry_after_seconds = retry_after_seconds

    def as_dict(self):
        payload = {"outcome": self.outcome}
        if self.outcome in (ANSWERED, DEGRADED_BUT_ANSWERED):
            payload["body"] = self.body
            payload["citations"] = list(self.citations)
            payload["degradation_level"] = self.degradation_level
            if self.outcome == DEGRADED_BUT_ANSWERED:
                payload["reduced"] = list(self.reduced)
        else:
            payload["reason"] = self.reason
            # Only a capacity refusal carries retry-after. A trust withhold must never imply that retrying harder,
            # or later, would produce an answer: the request is not one we may answer.
            if self.outcome == CAPACITY_REFUSED:
                payload["retry_after_seconds"] = self.retry_after_seconds
        return payload


def answered(body, citations, degradation_level=0, reduced=()):
    """An answer. Reaching this constructor means the trust path ran and passed — see trust.py, which is the only
    caller permitted to reach it."""
    if reduced:
        return Response(DEGRADED_BUT_ANSWERED, body=body, citations=citations, reduced=reduced,
                        degradation_level=degradation_level)
    return Response(ANSWERED, body=body, citations=citations, degradation_level=degradation_level)


def capacity_refused(reason, retry_after_seconds):
    """'I cannot serve this request now.' A statement about our capacity, carrying honest guidance."""
    return Response(CAPACITY_REFUSED, reason=reason, retry_after_seconds=retry_after_seconds)


def trust_withheld(reason):
    """'I must not answer this request.' Never carries retry-after: no amount of retrying makes it answerable."""
    return Response(TRUST_WITHHELD, reason=reason)
