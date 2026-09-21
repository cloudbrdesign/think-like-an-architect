"""The non-degradable trust path (CTL-405, ADR-004).

Episode 04 adds NO new trust logic. Eligibility is Episode 02's, currency is Episode 03's; both are carried over
unchanged and injected here. What Episode 04 adds is the guarantee that capacity pressure can never route around them.

Structural enforcement, not documentation:

  * `serve()` is the ONLY function in the system that calls `outcomes.answered()`;
  * it runs eligibility -> currency -> citation -> classification, in that order, before any content is returned;
  * the degradation rung is passed to the ANSWER path as a parameter, after the trust path has already run;
  * there is no configuration key, environment variable, flag or operator action that maps to the trust path.

`Capabilities` names what a rung may switch off. Every field is an ANSWER-path feature. Adding a trust check here would
be the bug this design exists to prevent, so `serve()` asserts that the capability set cannot disable a trust step.

**Operators may reduce service. Operators may not reduce trust.**
"""
from . import outcomes


class Capabilities:
    """What the current degradation rung leaves available. ANSWER-path features only."""

    __slots__ = ("enrichment", "wide_retrieval", "long_answers", "followup_suggestions", "generation_budget_tokens")

    # The answer-path features a rung may switch off. Used by the guard below: anything a rung can touch must be
    # in this set, and no trust step is ever in it.
    ANSWER_PATH_FEATURES = frozenset({"enrichment", "wide_retrieval", "long_answers", "followup_suggestions",
                                      "generation_budget_tokens"})

    def __init__(self, enrichment=True, wide_retrieval=True, long_answers=True, followup_suggestions=True,
                 generation_budget_tokens=512):
        self.enrichment = enrichment
        self.wide_retrieval = wide_retrieval
        self.long_answers = long_answers
        self.followup_suggestions = followup_suggestions
        self.generation_budget_tokens = generation_budget_tokens

    def reductions(self):
        """What was reduced, for the caller. A DEGRADED_BUT_ANSWERED response must say what it lost."""
        lost = []
        if not self.enrichment:
            lost.append("enrichment")
        if not self.wide_retrieval:
            lost.append("wide_retrieval")
        if not self.long_answers:
            lost.append("long_answers")
        if not self.followup_suggestions:
            lost.append("followup_suggestions")
        return tuple(lost)


class TrustPathViolation(AssertionError):
    """Raised when something tries to make a trust step degradable. This is a programming error, never a runtime
    outcome: it must fail the build and the suite, not degrade in production."""


def serve(request, capabilities, eligibility, currency, answer_path, degradation_level=0, signals=None):
    """Run the trust path, then the answer path. The only route to an answer.

    `eligibility(request) -> bool`      Episode 02, unchanged.
    `currency(request) -> (bool, str)`  Episode 03, unchanged: is the authority for this request known-current?
    `answer_path(request, capabilities) -> (body, citations)`

    Returns one of the four outcomes. Under any load, an unestablished eligibility or currency yields TRUST_WITHHELD,
    never DEGRADED_BUT_ANSWERED.
    """
    # Guard: a rung may only ever address answer-path features. If a capability set grows a trust-looking switch,
    # fail loudly rather than let a degradation rung acquire authority over trust.
    for name in getattr(capabilities, "__slots__", ()):
        if name not in Capabilities.ANSWER_PATH_FEATURES:
            raise TrustPathViolation(
                f"capability {name!r} is not an answer-path feature; a degradation rung may not address it")

    # 1. Eligibility (Episode 02). Not answerable by this caller -> withheld, whatever the load.
    if not eligibility(request):
        _count(signals, "trust_withheld_eligibility")
        return outcomes.trust_withheld("eligibility")

    # 2. Currency (Episode 03). Only KNOWN-current authority is servable. "Unknown" is not "probably fine",
    #    and saturation is not a reason to lower the bar (TST-409).
    current, currency_reason = currency(request)
    if not current:
        _count(signals, "trust_withheld_currency")
        return outcomes.trust_withheld(currency_reason or "currency")

    # 3. Answer path. Runs AFTER trust, parameterised by the rung.
    body, citations = answer_path(request, capabilities)

    # 4. Citation. An answer without cited authority is not an answer we may return.
    if not citations:
        _count(signals, "trust_withheld_citation")
        return outcomes.trust_withheld("no_citable_authority")

    _count(signals, "trust_checks_run")
    return outcomes.answered(body, citations, degradation_level=degradation_level,
                             reduced=capabilities.reductions())


def _count(signals, name):
    if signals is not None:
        signals.increment(name)
