"""Bounded recovery (CTL-411, ADR-008).

Recovery is part of the architecture, not what happens afterwards. Two rules:

  * the backlog is disposed of BY AGE, not replayed — replaying a backlog is how recovery outlasts the incident;
  * permits return in stages, with a dwell time at each stage, so the system does not invite the whole waiting
    population back at once and immediately re-saturate.
"""


class Ramp:
    """Staged permit restoration: 2 -> 3 -> 4, dwelling at each step."""

    def __init__(self, params, clock):
        self._steps = list(params.recovery_ramp_permits)
        self._dwell = params.recovery_ramp_step_seconds
        self._clock = clock
        self._index = None
        self._entered_at = None

    @property
    def active(self):
        return self._index is not None

    def begin(self):
        self._index = 0
        self._entered_at = self._clock()
        return self._steps[0]

    def current(self):
        return self._steps[self._index] if self.active else None

    def advance(self):
        """Move to the next stage once the dwell time has passed. Returns the permit count now in force, and None
        once the ramp has completed and normal capacity is restored."""
        if not self.active:
            return None
        if self._clock() - self._entered_at < self._dwell:
            return self._steps[self._index]
        if self._index + 1 < len(self._steps):
            self._index += 1
            self._entered_at = self._clock()
            return self._steps[self._index]
        self._index = None
        self._entered_at = None
        return None
