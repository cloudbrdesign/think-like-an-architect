"""The downstream permit broker (P4, CTL-408, ADR-005).

The model service is a boundary we do not control. Its quotas are per-account and token-based, so our capacity and its
capacity are different numbers — the mistake the incident made was assuming application concurrency was the limit.

Two bounds, because the boundary has two: concurrent calls AND a token budget per minute. A rejection from the
boundary is classified as SATURATION, not failure: it means we asked for more than our share, and the correct response
is to ask for less, not to retry harder.

Adaptive reduction engages on throttling and restores gradually. Restoring instantly would simply rebuild the
condition that caused the throttling.
"""
import collections
import threading

# Saturation is a CURRENT condition, so it is measured over a recent window. A lifetime average would mean that a
# boundary which rejected once early on still reads as saturated hours later, and the degradation ladder above it
# could never step back down — recovery would never complete. This is the window over which "are we being rejected?"
# is answered. It is deliberately the same order as the buffer's age bound and the ladder's hysteresis: if this window
# is much longer than those, the ladder cannot step down until it expires, and recovery takes longer than the incident.
REJECT_WINDOW_SECONDS = 10.0


class DownstreamSaturated(Exception):
    """The boundary refused, or we declined to ask. Saturation, not failure."""


class PermitBroker:
    def __init__(self, permits, token_budget_per_minute, clock, signals=None):
        self._configured = permits
        self._limit = permits
        self._tokens = token_budget_per_minute
        self._budget = token_budget_per_minute
        self._window_start = clock()
        self._in_use = 0
        self._clock = clock
        self._signals = signals
        self._lock = threading.Lock()
        self._calls = collections.deque()
        self._rejections = collections.deque()

    @property
    def adaptive_limit(self):
        return self._limit

    def reject_ratio(self):
        """The share of recent attempts the boundary refused. Zero when nothing has been attempted recently."""
        now = self._clock()
        self._prune(now)
        calls = len(self._calls)
        return (len(self._rejections) / calls) if calls else 0.0

    def _prune(self, now):
        for series in (self._calls, self._rejections):
            while series and now - series[0] > REJECT_WINDOW_SECONDS:
                series.popleft()

    def _roll_window(self, now):
        if now - self._window_start >= 60:
            self._window_start = now
            self._budget = self._tokens

    def acquire(self, estimated_tokens):
        """Take a permit and reserve tokens, or raise DownstreamSaturated. Never queues: a call we cannot make now is
        a capacity fact the caller must handle, not a wait we can hide."""
        now = self._clock()
        with self._lock:
            self._calls.append(now)
            self._prune(now)
            self._roll_window(now)
            if self._in_use >= self._limit:
                self._rejections.append(now)
                self._note("downstream_rejected_permits")
                raise DownstreamSaturated("no downstream permit free")
            if estimated_tokens > self._budget:
                self._rejections.append(now)
                self._note("downstream_rejected_tokens")
                raise DownstreamSaturated("downstream token budget exhausted for this window")
            self._in_use += 1
            self._budget -= estimated_tokens
            return True

    def release(self):
        with self._lock:
            if self._in_use:
                self._in_use -= 1

    def throttled(self):
        """The boundary itself throttled us: ask for less. Halve, never below one — one permit still makes progress,
        zero would convert saturation into an outage of our own making."""
        with self._lock:
            self._limit = max(1, self._limit // 2)
            self._rejections.append(self._clock())
            self._note("downstream_adaptive_reduction")
            return self._limit

    def restore_step(self):
        """Give back one permit at a time as conditions allow (ADR-008)."""
        with self._lock:
            if self._limit < self._configured:
                self._limit += 1
                self._note("downstream_adaptive_restore")
            return self._limit

    def in_use(self):
        return self._in_use

    def _note(self, name):
        if self._signals is not None:
            self._signals.increment(name)
