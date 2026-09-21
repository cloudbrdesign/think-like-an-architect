"""Admission control: partition permits, fair share, retry budget, single flight (P1, CTL-401/402/407).

Admission is ours. The edge throttle is a cheap outer filter, never the guarantee — API Gateway documents its
throttling as best-effort targets rather than guaranteed ceilings, so the architecture may not rest on it.

Refusing is not failing. A request refused at admission costs almost nothing and tells the caller the truth
immediately; the same request queued costs capacity and tells the caller nothing.
"""
import random
import threading

from . import outcomes


class RetryBudget:
    """Server-side retry budget per request identity (CTL-407, ADR-006).

    The client is not trusted to bound its own retries — the incident's turning point was retry amplification. The
    budget lives here, and the jittered retry-after exists so returning clients spread rather than arrive together.
    """

    def __init__(self, allowed, window_seconds, clock):
        self._allowed = allowed
        self._window = window_seconds
        self._clock = clock
        self._seen = {}
        self._lock = threading.Lock()

    def accept(self, identity):
        """True if this attempt is within budget. Attempts beyond it are refused without consuming capacity."""
        now = self._clock()
        with self._lock:
            attempts = [t for t in self._seen.get(identity, ()) if now - t < self._window]
            # The first attempt is not a retry; the budget bounds the retries that follow it.
            if len(attempts) > self._allowed:
                self._seen[identity] = attempts
                return False
            attempts.append(now)
            self._seen[identity] = attempts
            return True


class Permits:
    """A bounded pool with per-domain fair share (CTL-401, CTL-402).

    One fairness domain must not consume the capacity needed by all others. Each domain holds its own share; the
    elastic middle is borrowable but reclaimed as soon as its owner needs it.
    """

    def __init__(self, total, per_domain, domains):
        self._total = total
        self._per_domain = per_domain
        self._domains = tuple(domains)
        self._in_use = {d: 0 for d in self._domains}
        self._lock = threading.Lock()

    @property
    def total(self):
        return self._total

    def set_total(self, total):
        """Used by the recovery ramp (CTL-411) and adaptive reduction. Never by a caller."""
        with self._lock:
            self._total = total

    def in_use(self, domain=None):
        if domain is None:
            return sum(self._in_use.values())
        return self._in_use.get(domain, 0)

    def acquire(self, domain):
        """Grant a permit if the domain is within its share, or if borrowing would not eat another domain's share.

        The borrow rule is the whole point: free capacity is not the same as available capacity. A permit that is
        idle but reserved for a quiet domain must stay idle, or the quiet domain is starved the moment it returns —
        which is precisely the failure TST-402 exists to catch.
        """
        with self._lock:
            if domain not in self._in_use:
                self._in_use[domain] = 0
            free = self._total - sum(self._in_use.values())
            if free <= 0:
                return False
            if self._in_use[domain] < self._per_domain:
                self._in_use[domain] += 1          # within its own guaranteed share
                return True
            # Above its share: it may take only what no other domain is still owed.
            owed_to_others = sum(max(0, self._per_domain - used)
                                 for other, used in self._in_use.items() if other != domain)
            if free - owed_to_others <= 0:
                return False
            self._in_use[domain] += 1
            return True

    def release(self, domain):
        with self._lock:
            if self._in_use.get(domain):
                self._in_use[domain] -= 1


class SingleFlight:
    """One in-flight request per user identity (CTL-407). A repeat coalesces onto the first rather than duplicating
    work — repetition must be safe."""

    def __init__(self):
        self._active = set()
        self._lock = threading.Lock()

    def enter(self, identity):
        with self._lock:
            if identity in self._active:
                return False
            self._active.add(identity)
            return True

    def leave(self, identity):
        with self._lock:
            self._active.discard(identity)


def retry_after(base_seconds, rng=None):
    """Jittered retry-after. Without jitter, every refused caller returns at the same instant and rebuilds the burst
    that caused the refusal (ADR-006, ADR-008)."""
    rng = rng or random
    return round(base_seconds * (0.5 + rng.random()), 3)


def refuse_capacity(reason, base_seconds, signals=None, rng=None):
    if signals is not None:
        signals.increment("capacity_refused")
        signals.increment(f"capacity_refused_{reason}")
    return outcomes.capacity_refused(reason, retry_after(base_seconds, rng))
