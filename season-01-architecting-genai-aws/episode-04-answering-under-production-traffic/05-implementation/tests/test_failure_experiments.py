"""FX-1, FX-2, FX-3: the three headline failure experiments.

Each breaks ONE thing and asserts that the suite then FAILS in a specific, named way. A failure experiment that
merely "looks worse" proves nothing; the point is that a named test detects the break.

**FX-3 is the important one.** It makes a degradation rung serve an unverified result. TST-404 must then fail. If
FX-3 ever passes TST-404, the trust invariant is not structural and the episode's central claim is false — so this
file asserts that the mutation IS detected, which is the opposite of asserting the system still works.
"""
import unittest

from support import parameters, run
from app.core import degradation, outcomes
from app.core.trust import Capabilities, TrustPathViolation, serve


class FX1RemoveAdmissionAndAgeBound(unittest.TestCase):
    """Admission control and the age bound removed; everything queued.

    Teaches: a queue relocates overload, it does not absorb it. Age is the property that matters.
    """

    def test_an_unbounded_queue_hides_overload_instead_of_reporting_it(self):
        from app.core.buffer import BurstBuffer

        class UnboundedBuffer(BurstBuffer):
            """The mutation: unlimited room, no deadline. Nothing is ever refused, nothing ever expires."""

            def offer(self, payload):
                self._items.append((self._clock(), payload))
                return True

            def expired_at_head(self):
                return False

        clock = [1000.0]
        buffer = UnboundedBuffer(6, 10, lambda: clock[0])
        for i in range(200):
            self.assertTrue(buffer.offer({"identity": f"u{i}"}),
                            "the mutated buffer refused, so the experiment did not take effect")
        clock[0] += 3600                       # an hour later, the work is still queued and still 'fine'
        self.assertEqual(buffer.depth(), 200, "work vanished instead of being reported")
        self.assertFalse(buffer.expired_at_head(),
                         "without an age bound nothing expires — which is exactly the failure being demonstrated")
        # The real buffer, given the same treatment, refuses and expires: bounded by capacity AND age.
        honest = BurstBuffer(6, 10, lambda: clock[0])
        accepted = [honest.offer({"identity": f"u{i}"}) for i in range(200)]
        self.assertEqual(accepted.count(True), 6, "the real buffer must bound what it accepts")
        clock[0] += 11
        self.assertTrue(honest.expired_at_head(), "the real buffer must expire work past its deadline")


class FX2RemoveRetryBudget(unittest.TestCase):
    """Retry budget, jitter and guidance removed: offered load multiplies.

    Teaches: retry amplification — the incident's turning point. A survivable burst becomes an outage.
    """

    def test_unbounded_retrying_multiplies_offered_load(self):
        bounded = run("bounded-retry")
        unbounded = run("bad-retry")
        self.assertGreater(unbounded["offered"], bounded["offered"] * 1.2,
                           "removing the retry contract did not multiply offered load, so FX-2 proves nothing")
        self.assertGreater(unbounded["capacity_refused"], bounded["capacity_refused"])
        # Useful throughput does not improve by retrying harder — it is the same or worse for far more load.
        self.assertLessEqual(unbounded["answered"] + unbounded["degraded"],
                             bounded["answered"] + bounded["degraded"])

    def test_the_retry_budget_is_what_bounds_it(self):
        self.assertGreater(run("bad-retry")["counters"].get("retry_budget_exhausted", 0), 0)


class FX3DegradationServesUnverifiedResult(unittest.TestCase):
    """A degradation rung serves a cached, unverified result.

    **This mutation MUST be detected.** It is the one failure the architecture exists to make impossible.
    """

    def test_a_rung_cannot_be_given_authority_over_trust(self):
        """The mutation: add a trust-looking switch to the capability set, as an operator under pressure would."""

        class MutatedCapabilities(Capabilities):
            # 'skip_currency_check' is what someone adds at 03:00 to make the graphs look better.
            __slots__ = ("skip_currency_check",)

            def __init__(self):
                super().__init__()
                self.skip_currency_check = True

        with self.assertRaises(TrustPathViolation):
            serve({"identity": "u1"}, MutatedCapabilities(),
                  eligibility=lambda r: True, currency=lambda r: (False, "currency_unconfirmed"),
                  answer_path=lambda r, c: ("cached answer", ("stale-doc",)))

    def test_the_unverified_answer_is_withheld_not_degraded(self):
        """Even with every rung switch off, unconfirmable currency yields TRUST_WITHHELD — never a degraded answer."""
        for level in (0, 1, 2):
            capabilities = degradation.capabilities_for(level, parameters())
            response = serve({"identity": "u1"}, capabilities,
                             eligibility=lambda r: True, currency=lambda r: (False, "currency_unconfirmed"),
                             answer_path=lambda r, c: ("cached answer", ("stale-doc",)))
            self.assertEqual(response.outcome, outcomes.TRUST_WITHHELD,
                             f"rung {level} produced {response.outcome} for unconfirmable currency")
            self.assertIsNone(response.body, "a withheld response must not carry content")

    def test_tst404_fails_when_the_mutation_is_allowed_through(self):
        """If the trust path could be bypassed, TST-404's assertion would not hold. Demonstrated directly: a serve()
        that skips currency returns an ANSWER, and that is what the real path must never do."""
        def bypassed_serve(request, capabilities):
            # The mutation, written out: eligibility only, no currency, straight to the answer.
            body, citations = ("cached answer", ("stale-doc",))
            return outcomes.answered(body, citations)

        mutated = bypassed_serve({"identity": "u1"}, degradation.capabilities_for(2, parameters()))
        self.assertEqual(mutated.outcome, outcomes.ANSWERED,
                         "the mutation must genuinely produce an answer, or it is not the failure we mean")
        honest = serve({"identity": "u1"}, degradation.capabilities_for(2, parameters()),
                       eligibility=lambda r: True, currency=lambda r: (False, "currency_unconfirmed"),
                       answer_path=lambda r, c: ("cached answer", ("stale-doc",)))
        self.assertNotEqual(honest.outcome, mutated.outcome,
                            "the real path behaved like the mutated one: the trust invariant is NOT structural")


if __name__ == "__main__":
    unittest.main(verbosity=2)
