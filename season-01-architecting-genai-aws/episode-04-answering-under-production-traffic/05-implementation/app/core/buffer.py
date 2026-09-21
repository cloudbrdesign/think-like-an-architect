"""The age-bounded burst buffer (P2, CTL-403, ADR-002).

A queue does not absorb overload; it relocates it. What makes this buffer safe is not its size but its **age bound**:
work that has waited past its deadline can no longer be useful to the caller, so it leaves through an explicit
CAPACITY_REFUSED rather than being executed late or dropped silently.

Two bounds, both enforced:
  * capacity — how many items may wait;
  * age      — how long any item may wait.

Expiry is checked BEFORE execution, never after. Executing an expired item spends capacity on an answer nobody is
waiting for, which is how a system stays saturated long after the burst has passed (FX-1 demonstrates exactly this).
"""


class Expired(Exception):
    """The item passed its deadline while waiting. Carries the age so the refusal can be honest."""

    def __init__(self, age_seconds):
        super().__init__(f"expired after {age_seconds:.3f}s")
        self.age_seconds = age_seconds


class BurstBuffer:
    def __init__(self, capacity, max_age_seconds, clock):
        self._capacity = capacity
        self._max_age = max_age_seconds
        self._clock = clock
        self._items = []          # (enqueued_at, payload)

    @property
    def capacity(self):
        return self._capacity

    @property
    def max_age_seconds(self):
        return self._max_age

    def depth(self):
        return len(self._items)

    def oldest_age(self):
        """Age of the oldest waiting item — the signal that leads. Depth alone cannot tell a draining queue from a
        stuck one (ADR-007)."""
        if not self._items:
            return 0.0
        return self._clock() - self._items[0][0]

    def peek(self):
        """The head item, without removing it. Its deadline keeps running.

        This exists so a consumer can ask "whose is this, and may I run it?" without taking it out and putting it
        back — re-enqueuing would restart its clock, and an item whose clock restarts can never expire, which would
        make the age bound unenforceable.
        """
        return self._items[0][1] if self._items else None

    def expired_at_head(self):
        """True when the head item is already past its deadline and must leave as an explicit refusal."""
        return bool(self._items) and self.oldest_age() > self._max_age

    def offer(self, payload):
        """Accept the item if there is room. Returns False when full: the caller must then refuse explicitly."""
        if len(self._items) >= self._capacity:
            return False
        self._items.append((self._clock(), payload))
        return True

    def take(self):
        """Take the next item that is still within its deadline.

        Raises `Expired` for each item found past its deadline, one per call, so the caller can emit one explicit
        CAPACITY_REFUSED per expired item — expired work must leave through an outcome, not vanish.
        Returns None when the buffer is empty.
        """
        while self._items:
            enqueued_at, payload = self._items[0]
            age = self._clock() - enqueued_at
            self._items.pop(0)
            if age > self._max_age:
                raise Expired(age)
            return payload
        return None

    def drain_expired(self):
        """Remove every item already past its deadline. Returns their ages, so each becomes its own refusal.

        Used by the recovery path (CTL-411): a backlog is disposed of by age, not replayed. Replaying a backlog is how
        recovery outlasts the incident that caused it.
        """
        now = self._clock()
        expired, keep = [], []
        for enqueued_at, payload in self._items:
            age = now - enqueued_at
            (expired if age > self._max_age else keep).append(age if age > self._max_age else (enqueued_at, payload))
        self._items = keep
        return expired
