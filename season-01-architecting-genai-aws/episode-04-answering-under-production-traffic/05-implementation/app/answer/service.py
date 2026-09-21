"""The answering service (P3): admission -> buffer -> trust path -> answer path -> outcome.

This module is the assembly, not new policy. Every rule it applies lives in `app/core`, and the one thing it must
never do is construct an answer itself: answers come only from `trust.serve()`, refusals only from the admission and
buffer paths. That is what makes the trust invariant structural rather than a convention.

**Two phases, because the real system has two.** `admit()` decides whether the request may consume capacity;
`execute()` spends it. Between them the request is in flight, holding a permit. A synchronous caller uses `handle()`,
which is simply the two in sequence — there is no second implementation of the rules.

Order within admission is deliberate:
  1. retry budget  — a request over budget never consumes capacity;
  2. single flight — a repeat coalesces rather than duplicating work;
  3. permits       — fair share within the bounded pool;
  4. buffer        — only a short, age-bounded wait, never an unbounded queue.
Then, in execute():
  5. trust path    — eligibility, currency, citation; not addressable by any rung;
  6. answer path   — parameterised by the current degradation rung.
"""
from ..core import admission, degradation
from ..core.recovery import Ramp
from ..core.buffer import Expired
from ..core.downstream import DownstreamSaturated
from ..core.trust import serve


class Ticket:
    """An admitted request, holding one permit until `execute()` releases it."""

    __slots__ = ("request", "domain", "identity", "level", "admitted_at", "downstream_held")

    def __init__(self, request, domain, identity, level, admitted_at):
        self.downstream_held = False
        self.request = request
        self.domain = domain
        self.identity = identity
        self.level = level
        self.admitted_at = admitted_at


class AnsweringService:
    def __init__(self, params, clock, permits, burst_buffer, ladder, broker, signals,
                 eligibility, currency, answer_path, rng=None):
        self._p = params
        self._clock = clock
        self._permits = permits
        self._buffer = burst_buffer
        self._ladder = ladder
        self._broker = broker
        self._signals = signals
        self._eligibility = eligibility
        self._currency = currency
        self._answer_path = answer_path
        self._rng = rng
        self._retries = admission.RetryBudget(params.retry_budget_per_identity,
                                              params.retry_budget_window_seconds, clock)
        self._single_flight = admission.SingleFlight()
        self._ramp = Ramp(params, clock)
        self._full_permits = params.answering_permits_total
        self._was_shedding = False

    # ── signals the operator sees before users do (CTL-410) ────────────────────────────────────────────────────────
    def publish_signals(self):
        s = self._signals
        s.gauge("buffer_depth", self._buffer.depth())
        s.gauge("buffer_age_seconds", round(self._buffer.oldest_age(), 3))
        s.gauge("concurrency_in_use", self._permits.in_use())
        s.gauge("permits_current", self._permits.total)
        s.gauge("degradation_level", self._ladder.level)
        s.gauge("downstream_permits_in_use", self._broker.in_use())
        s.gauge("downstream_adaptive_limit", self._broker.adaptive_limit)
        for domain in self._p.fairness_domains:
            s.gauge(f"concurrency_{domain}", self._permits.in_use(domain))

    def tick(self):
        """Re-evaluate the rung and advance recovery. Must be called even when nothing arrives.

        A system under no load is exactly when the rung should be falling, so leaving the ladder to be updated only by
        incoming requests would leave a quiet system stuck at the rung its last burst reached — which is what the
        first version of this code did.
        """
        level = self._ladder.update(self._buffer.oldest_age(), self._broker.reject_ratio())

        backlog_clear = self._buffer.depth() == 0
        if backlog_clear and self._was_shedding and not self._ramp.active:
            # Pressure has cleared. Capacity returns in stages, not all at once: inviting the whole waiting
            # population back together is how a recovery becomes the next incident (ADR-008).
            self._was_shedding = False
            self._permits.set_total(self._ramp.begin())
            self._signals.increment("recovery_ramp_started")
        elif self._ramp.active:
            step = self._ramp.advance()
            if step is None:
                self._permits.set_total(self._full_permits)
                self._signals.increment("recovery_complete")
                self._signals.gauge("recovery_state", 0)
            else:
                self._permits.set_total(step)
                self._signals.gauge("recovery_state", step)
        elif level > degradation.NORMAL:
            self._was_shedding = True

        # Give the downstream boundary back one permit at a time as conditions allow.
        if level == degradation.NORMAL and self._broker.reject_ratio() == 0:
            self._broker.restore_step()

        self.publish_signals()
        return level

    # ── phase 1: may this request consume capacity? ────────────────────────────────────────────────────────────────
    def admit(self, request):
        """Returns `(ticket, None)` when admitted, or `(None, response)` when refused.

        A refusal here costs almost nothing and tells the caller the truth immediately. The same request queued
        without bound would cost capacity and tell the caller nothing.
        """
        identity = request["identity"]
        domain = request.get("domain", self._p.fairness_domains[0])
        self._signals.increment("offered")

        level = self._ladder.update(self._buffer.oldest_age(), self._broker.reject_ratio())

        if not self._retries.accept(identity):
            self._signals.increment("retry_budget_exhausted")
            return None, admission.refuse_capacity("retry_budget_exhausted", 1.0, self._signals, self._rng)

        if not self._single_flight.enter(identity):
            self._signals.increment("coalesced")
            return None, admission.refuse_capacity("already_in_flight", 0.5, self._signals, self._rng)

        if not self._permits.acquire(domain):
            self._signals.increment(f"refused_by_domain_{domain}")
            if not self._buffer.offer(request):
                self._single_flight.leave(identity)
                self._signals.increment("buffer_full")
                return None, admission.refuse_capacity("buffer_full", 2.0, self._signals, self._rng)
            self._signals.increment("buffered")
            self.publish_signals()
            return None, None          # waiting in the buffer; nothing to tell the caller yet

        self.publish_signals()
        return Ticket(request, domain, identity, level, self._clock()), None

    def promote_from_buffer(self):
        """Take the next still-valid buffered item and admit it, if a permit is now free.

        Expiry is checked BEFORE execution: expired work leaves through an explicit CAPACITY_REFUSED rather than being
        executed late (CTL-403). Returns `(ticket, response)`; both may be None when there is nothing to do.
        """
        if self._buffer.depth() == 0:
            return None, None

        # Expiry is checked first, and independently of whether a permit is free: an item past its deadline must
        # leave through an explicit outcome whatever the state of the pool.
        if self._buffer.expired_at_head():
            expiring = self._buffer.peek()
            try:
                self._buffer.take()
            except Expired as expired:
                self._signals.increment("expired_before_execution")
                self._signals.gauge("last_expiry_age_seconds", round(expired.age_seconds, 3))
                # Release the in-flight slot the request held while it waited, or a caller whose request expired
                # could never ask again — a refusal must not also become a lockout.
                self._single_flight.leave(expiring["identity"])
                return None, admission.refuse_capacity("buffer_age_exceeded", 2.0, self._signals, self._rng)

        waiting = self._buffer.peek()
        if waiting is None:
            return None, None
        domain = waiting.get("domain", self._p.fairness_domains[0])
        if not self._permits.acquire(domain):
            return None, None                  # stays exactly where it is, and keeps ageing toward its deadline
        waiting = self._buffer.take()
        level = self._ladder.update(self._buffer.oldest_age(), self._broker.reject_ratio())
        return Ticket(waiting, domain, waiting["identity"], level, self._clock()), None

    def start_answer(self, ticket):
        """Take a downstream permit for the model call this request is about to make.

        The permit is held for as long as the call is in flight, not just for the instant of dispatch — otherwise two
        overlapping answers never contend and the boundary can never be seen to saturate, which is the whole of
        TST-408. Returns `None` when the answer may proceed, or a CAPACITY_REFUSED response when the boundary has no
        room: saturation is a capacity fact, reported as one.
        """
        try:
            self._broker.acquire(degradation.capabilities_for(ticket.level, self._p).generation_budget_tokens)
            ticket.downstream_held = True
            return None
        except DownstreamSaturated as saturated:
            self._signals.increment("downstream_saturated")
            self._broker.throttled()
            self._permits.release(ticket.domain)
            self._single_flight.leave(ticket.identity)
            self.publish_signals()
            response = admission.refuse_capacity(f"downstream_saturated:{saturated}", 3.0, self._signals, self._rng)
            self._signals.increment(response.outcome.lower())
            return response

    # ── phase 2: spend the capacity ────────────────────────────────────────────────────────────────────────────────
    def execute(self, ticket):
        """Run the trust path, then the answer path, then release the permit."""
        try:
            capabilities = degradation.capabilities_for(ticket.level, self._p)
            response = serve(ticket.request, capabilities,
                             eligibility=self._eligibility, currency=self._currency,
                             answer_path=self._wrap_answer_path(ticket), degradation_level=ticket.level,
                             signals=self._signals)
        except DownstreamSaturated as saturated:
            # The boundary is the constraint, not us. Saturation is a capacity fact, reported as one.
            self._signals.increment("downstream_saturated")
            self._broker.throttled()
            response = admission.refuse_capacity(f"downstream_saturated:{saturated}", 3.0, self._signals, self._rng)
        finally:
            if ticket.downstream_held:
                self._broker.release()
                ticket.downstream_held = False
            self._permits.release(ticket.domain)
            self._single_flight.leave(ticket.identity)
            self.publish_signals()
        self._signals.increment(response.outcome.lower())
        return response

    def handle(self, request):
        """Synchronous convenience: admit, then execute. Used by the request-response entry point."""
        ticket, response = self.admit(request)
        if ticket is None:
            if response is None:                       # buffered, then promoted immediately
                ticket, response = self.promote_from_buffer()
            if ticket is None:
                return response
        refused = self.start_answer(ticket)
        return refused if refused is not None else self.execute(ticket)

    def _wrap_answer_path(self, ticket):
        """The answer path runs under the downstream permit `start_answer()` already took for this ticket."""
        def call(request, capabilities):
            if not ticket.downstream_held:
                self._broker.acquire(capabilities.generation_budget_tokens)
                ticket.downstream_held = True
            return self._answer_path(request, capabilities)
        return call
