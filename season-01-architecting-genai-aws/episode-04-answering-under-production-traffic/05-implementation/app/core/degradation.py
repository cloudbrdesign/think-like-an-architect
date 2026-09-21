"""The degradation ladder (CTL-406, ADR-004).

One value — `degradation_level` — computed from signals. Each rung is a set of feature switches on the ANSWER path
only. The trust path is not addressable from here: there is no key in this module that maps to eligibility, currency
or citation, and `trust.Capabilities` refuses to carry one.

Ordered, triggered, reversible, and hysteretic: stepping down one rung at a time after the trigger has been clear for
the hysteresis interval is what stops the system oscillating between rungs under a wobbling load.
"""
from .trust import Capabilities

NORMAL, DEGRADED_1, DEGRADED_2 = 0, 1, 2


def capabilities_for(level, params):
    """What remains available at each rung. Answer-path features only.

    Rung 1 drops the cheapest capability with the largest latency saving per unit of quality.
    Rung 2 protects the downstream boundary and shortens how long each request holds a permit.
    At every rung the full trust path still runs and citations are still returned.
    """
    if level >= DEGRADED_2:
        return Capabilities(enrichment=False, wide_retrieval=False, long_answers=False, followup_suggestions=False,
                            generation_budget_tokens=128)
    if level == DEGRADED_1:
        return Capabilities(enrichment=False, wide_retrieval=False, long_answers=True, followup_suggestions=True,
                            generation_budget_tokens=512)
    return Capabilities()


class Ladder:
    """Computes the current rung from observed signals, with hysteresis on the way down."""

    def __init__(self, params, clock):
        self._p = params
        self._clock = clock
        self._level = NORMAL
        self._clear_since = None

    @property
    def level(self):
        return self._level

    def update(self, buffer_age_seconds, downstream_reject_ratio):
        """Recompute the rung. Rises immediately when a trigger is met; falls one rung at a time, and only after the
        trigger has stayed clear for the hysteresis interval."""
        now = self._clock()
        if buffer_age_seconds > self._p.degradation_l2_buffer_age_seconds or \
                downstream_reject_ratio > self._p.degradation_l2_downstream_reject_ratio:
            target = DEGRADED_2
        elif buffer_age_seconds > self._p.degradation_l1_buffer_age_seconds:
            target = DEGRADED_1
        else:
            target = NORMAL

        if target > self._level:
            self._level = target           # pressure is answered at once
            self._clear_since = None
            return self._level

        if target < self._level:
            if self._clear_since is None:
                self._clear_since = now
            elif now - self._clear_since >= self._p.hysteresis_seconds:
                self._level -= 1           # one rung at a time
                self._clear_since = now if self._level > target else None
        else:
            self._clear_since = None
        return self._level

    def reason(self):
        return {NORMAL: "normal", DEGRADED_1: "buffer_age_above_l1",
                DEGRADED_2: "buffer_age_above_l2_or_downstream_saturated"}[self._level]
