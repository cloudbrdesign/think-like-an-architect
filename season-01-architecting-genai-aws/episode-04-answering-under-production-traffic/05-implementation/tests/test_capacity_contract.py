"""TST-401…411: the architecture's claims, proved against the real application code.

These run the production modules, not a model of them. The clock is deterministic so a lesson that appears once
appears every time — a scenario that only sometimes demonstrates its point is not evidence.
"""
import unittest

from support import run, parameters, outcomes_of


class TST401ThePromise(unittest.TestCase):
    """The stated capacity is real and measured, and is the anchor for every overload result."""

    def test_normal_load_is_answered_within_the_pool(self):
        result = run("normal")
        counts = outcomes_of(result)
        self.assertEqual(counts["capacity_refused"], 0, "the promise must hold at the stated load")
        self.assertEqual(counts["trust_withheld"], 0)
        self.assertEqual(counts["answered"], result["offered"])
        # The method is recorded with the evidence (OPS-004): every summary echoes the parameters that produced it.
        self.assertIn("demonstration_parameters", result)
        self.assertEqual(result["demonstration_parameters"]["answering_permits_total"],
                         parameters().answering_permits_total)


class TST402Fairness(unittest.TestCase):
    """One fairness domain cannot consume the capacity needed by all others (CTL-402)."""

    def test_a_flooding_depot_cannot_take_the_whole_pool(self):
        result = run("burst")                       # depot-north only
        p = parameters()
        peak_north = max(row["concurrency"] for row in result["timeline"])
        self.assertLessEqual(peak_north, p.fair_share_per_domain,
                             "a single depot took more than its share while the other was idle")

    def test_the_quiet_domain_keeps_its_share(self):
        from app.core.admission import Permits
        p = parameters()
        permits = Permits(p.answering_permits_total, p.fair_share_per_domain, p.fairness_domains)
        north, south = p.fairness_domains[0], p.fairness_domains[1]
        while permits.acquire(north):
            pass
        self.assertTrue(permits.acquire(south), "the quiet domain was starved by the flooding one")


class TST403BoundedExcess(unittest.TestCase):
    """The buffer is bounded by capacity AND age; expired work exits explicitly (CTL-403)."""

    def test_capacity_bound_holds(self):
        result = run("sustained")
        p = parameters()
        self.assertGreater(result["counters"].get("buffer_full", 0), 0,
                           "the capacity bound was never reached, so it was never demonstrated")
        self.assertLessEqual(max(row.get("buffer_age_seconds", 0) for row in result["timeline"]),
                             p.buffer_max_age_seconds + p.answer_duration_seconds_nominal)

    def test_age_bound_expires_work_before_execution(self):
        # A saturated boundary is SLOW before it refuses; that is what ages the buffer past its deadline.
        result = run("downstream-limit")
        expired = result["counters"].get("expired_before_execution", 0)
        self.assertGreater(expired, 0, "no item ever reached its deadline, so the age bound is unproven")
        self.assertEqual(expired, result["counters"].get("capacity_refused_buffer_age_exceeded", 0),
                         "every expired item must leave through an explicit CAPACITY_REFUSED")
        self.assertGreater(result["gauges"]["last_expiry_age_seconds"], parameters().buffer_max_age_seconds)


class TST404TheTrustInvariant(unittest.TestCase):
    """The central claim: capacity never converts unanswerable into answerable (CTL-404, CTL-405)."""

    def test_withheld_under_saturation_is_never_answered(self):
        result = run("withhold")
        self.assertGreater(result["trust_withheld"], 0, "nothing was withheld, so nothing was proved")
        self.assertGreater(result["capacity_refused"], 0, "the system was not actually saturated")
        withheld = result["counters"].get("trust_withheld_currency", 0)
        self.assertEqual(withheld, result["trust_withheld"],
                         "a withheld request was counted as something else")

    def test_the_four_outcomes_are_never_merged(self):
        result = run("withhold")
        counted = outcomes_of(result)
        self.assertEqual(sum(counted.values()), result["offered"],
                         "outcomes do not account for every offered request")
        # Distinctness is structural: a refusal carries retry-after, a withhold must never imply retrying would work.
        from app.core import outcomes
        self.assertIsNone(outcomes.trust_withheld("currency").as_dict().get("retry_after_seconds"))
        self.assertIsNotNone(outcomes.capacity_refused("buffer_full", 2.0).as_dict()["retry_after_seconds"])

    def test_no_rung_can_reach_the_trust_path(self):
        from app.core import degradation
        from app.core.trust import Capabilities
        p = parameters()
        for level in (0, 1, 2):
            capabilities = degradation.capabilities_for(level, p)
            for field in capabilities.__slots__:
                self.assertIn(field, Capabilities.ANSWER_PATH_FEATURES,
                              f"rung {level} can address {field!r}, which is not an answer-path feature")


class TST405WorkloadFloors(unittest.TestCase):
    """Neither workload starves; falling freshness is visible (CTL-401, CTL-409)."""

    def test_change_processing_survives_an_answering_flood(self):
        result = run("contention")
        self.assertGreater(result["counters"].get("change_applied", 0), 0,
                           "change processing was starved by answering")
        self.assertGreater(result["answered"] + result["degraded"], 0, "answering was starved by change processing")

    def test_freshness_is_reported_not_assumed(self):
        result = run("contention")
        self.assertIn("freshness_lag_seconds", result["gauges"])
        self.assertIn("watermark_stalled", result["gauges"])


class TST406DegradationLadder(unittest.TestCase):
    """Rungs are ordered, triggered and reversible; the trust path runs at every rung (CTL-406)."""

    def test_rungs_rise_with_pressure_and_fall_with_hysteresis(self):
        result = run("recover")
        levels = [row["degradation_level"] for row in result["timeline"]]
        self.assertEqual(max(levels), 2, "the second rung was never reached")
        self.assertEqual(levels[-1], 0, "the system never returned to normal")
        # It must come down one rung at a time, never jump straight from 2 to 0.
        descents = [(a, b) for a, b in zip(levels, levels[1:]) if b < a]
        self.assertTrue(all(a - b == 1 for a, b in descents), f"a rung was skipped on the way down: {descents}")

    def test_a_degraded_answer_says_what_it_lost(self):
        result = run("sustained")
        self.assertGreater(result["degraded"], 0)
        from app.core import degradation
        reduced = degradation.capabilities_for(1, parameters()).reductions()
        self.assertIn("enrichment", reduced)


class TST407RetryContract(unittest.TestCase):
    """Bounded retries keep offered load bounded (CTL-407)."""

    def test_unbounded_retrying_multiplies_offered_load(self):
        bounded = run("bounded-retry")
        bad = run("bad-retry")
        self.assertGreater(bad["offered"], bounded["offered"],
                           "the amplification contrast is the whole lesson and it did not appear")
        self.assertGreater(bad["counters"].get("retry_budget_exhausted", 0), 0,
                           "the retry budget never engaged")

    def test_repeats_coalesce_rather_than_duplicating_work(self):
        result = run("bad-retry")
        self.assertGreater(result["counters"].get("coalesced", 0) +
                           result["counters"].get("retry_budget_exhausted", 0), 0)


class TST408DownstreamBoundary(unittest.TestCase):
    """We never oversubscribe a boundary we do not control; saturation is not failure (CTL-408)."""

    def test_permits_cap_concurrent_calls_and_reduction_engages(self):
        result = run("downstream-limit")
        self.assertGreater(result["counters"].get("downstream_adaptive_reduction", 0), 0,
                           "adaptive reduction never engaged")
        self.assertLessEqual(result["gauges"]["downstream_adaptive_limit"], parameters().downstream_permits)

    def test_saturation_is_classified_as_capacity_not_error(self):
        result = run("downstream-limit")
        self.assertEqual(sum(outcomes_of(result).values()), result["offered"])


class TST409CurrencyUnderSaturation(unittest.TestCase):
    """Unconfirmable currency withholds, and is counted as its own outcome."""

    def test_currency_withholding_has_its_own_counter(self):
        result = run("withhold")
        self.assertGreater(result["counters"].get("trust_withheld_currency", 0), 0)
        self.assertEqual(result["counters"].get("trust_withheld_eligibility", 0), 0,
                         "an eligibility withhold was miscounted as a currency withhold")


class TST410Observability(unittest.TestCase):
    """Saturation is visible before users feel it; the signals stay distinct (CTL-410)."""

    def test_the_leading_signals_are_present(self):
        result = run("sustained")
        for signal in ("buffer_depth", "buffer_age_seconds", "concurrency_in_use", "degradation_level",
                       "downstream_adaptive_limit"):
            self.assertIn(signal, result["gauges"], f"{signal} is not emitted, so operators cannot see it")

    def test_refusal_reasons_are_not_merged(self):
        result = run("downstream-limit")
        reasons = [k for k in result["counters"] if k.startswith("capacity_refused_")]
        self.assertGreater(len(reasons), 1, "every refusal was given the same reason")


class TST411BoundedRecovery(unittest.TestCase):
    """Recovery is designed and bounded (CTL-411)."""

    def test_backlog_ages_out_and_permits_return_in_stages(self):
        result = run("recover")
        self.assertEqual(result["gauges"]["buffer_depth"], 0, "the backlog never drained")
        self.assertEqual(result["gauges"]["permits_current"], parameters().answering_permits_total,
                         "capacity never returned to normal")
        self.assertGreater(result["counters"].get("recovery_ramp_started", 0), 0,
                           "capacity returned without a staged ramp")

    def test_no_second_spike_after_recovery(self):
        result = run("recover")
        tail = result["timeline"][-5:]
        self.assertTrue(all(row["degradation_level"] == 0 for row in tail),
                        "the system re-degraded after recovering")


if __name__ == "__main__":
    unittest.main(verbosity=2)
