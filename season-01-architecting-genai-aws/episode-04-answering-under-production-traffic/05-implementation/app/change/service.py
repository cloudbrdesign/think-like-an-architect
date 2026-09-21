"""Change processing (P5, CTL-409, ADR-003) — Episode 03's workload at lab scale.

It exists here for one reason: to prove that the answering workload cannot starve it, and that when freshness does
fall behind, the fall is **visible** rather than silent. Episode 03's claim ("the derived copy is known-current")
quietly lapses the moment this workload stops running, and nothing in Episode 03 would have shown that.
"""


class ChangeProcessor:
    def __init__(self, params, clock, signals, apply_change):
        self._p = params
        self._clock = clock
        self._signals = signals
        self._apply = apply_change
        self._watermark = clock()
        self._last_progress = clock()
        self._floor = params.change_processing_floor
        self._in_flight = 0

    @property
    def watermark(self):
        return self._watermark

    def freshness_lag_seconds(self):
        return round(self._clock() - self._watermark, 3)

    def watermark_stalled(self, stall_threshold_seconds=20):
        return (self._clock() - self._last_progress) > stall_threshold_seconds

    def process(self, change):
        """Process one change. The floor is reserved concurrency in AWS; here it is the guarantee that this workload
        always has at least `change_processing_floor` in flight available to it."""
        if self._in_flight >= self._floor:
            self._signals.increment("change_deferred")
            return False
        self._in_flight += 1
        try:
            self._apply(change)
            self._watermark = self._clock()
            self._last_progress = self._watermark
            self._signals.increment("change_applied")
            return True
        finally:
            self._in_flight -= 1
            self.publish_signals()

    def idle(self):
        """No change is waiting, so the derived copy is current as of now.

        Freshness lag measures how far behind the authority the derived copy is. With nothing to apply there is
        nothing to be behind, so the watermark advances. Letting lag grow while idle would report staleness that does
        not exist, and would make the real stall in TST-405 indistinguishable from a quiet period.
        """
        self._watermark = self._clock()
        self._last_progress = self._watermark
        self.publish_signals()

    def publish_signals(self):
        self._signals.gauge("freshness_lag_seconds", self.freshness_lag_seconds())
        self._signals.gauge("watermark_stalled", 1 if self.watermark_stalled() else 0)
