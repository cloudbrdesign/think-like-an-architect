"""Eligibility (CTL-001), tier selection (D3 layer 1) and constraint construction (CTL-011 – CTL-013, D3 layer 2)."""
import inspect
import json
import unittest

import support  # noqa: F401
from core import constraints, eligibility as e, tier_selection as t
from core.reason_codes import REFUSED_CONSTRAINT_INCOMPLETE, Refusal


def decision(domains=(), cases=()):
    return e.allow("sub", domains, cases, 1, 1)


def operators(node, found=None):
    found = set() if found is None else found
    for key, value in node.items():
        found.add(key)
        if isinstance(value, list):
            for child in value:
                if isinstance(child, dict):
                    operators(child, found)
    return found


class Eligibility(unittest.TestCase):
    def test_rule(self):
        d = decision(["BID-ORION"], ["SI-0417"])
        self.assertTrue(e.is_eligible(d, "INTERNAL", "NONE"))
        self.assertTrue(e.is_eligible(d, "CONFIDENTIAL", "BID-ORION"))
        self.assertFalse(e.is_eligible(d, "CONFIDENTIAL", "FIN-REPORTING"))
        self.assertTrue(e.is_eligible(d, "RESTRICTED", "SI-0417"))
        self.assertFalse(e.is_eligible(d, "RESTRICTED", "HR-2031"))

    def test_domain_membership_never_satisfies_a_case(self):
        self.assertFalse(e.is_eligible(decision(["HR-2031"]), "RESTRICTED", "HR-2031"))

    def test_non_allow_decisions_are_never_eligible(self):
        for status, outcome in ((e.DENIED, "REFUSED_NO_ACTIVE_EMPLOYMENT"), (e.UNAVAILABLE, "REFUSED_AUTHORIZATION_UNAVAILABLE")):
            self.assertFalse(e.is_eligible(e.refuse("sub", status, outcome), "INTERNAL", "NONE"))
        self.assertFalse(e.is_eligible(None, "INTERNAL", "NONE"))

    def test_unknown_or_non_canonical_labels_are_not_eligible(self):
        d = decision(["BID-ORION"])
        for label in ("internal", "CONFIDENTAIL", "", None, "PUBLIC"):
            self.assertFalse(e.is_eligible(d, label, "NONE"))
            self.assertFalse(e.is_eligible(d, label, "BID-ORION"))

    def test_untrusted_identifiers_rejected(self):
        for bad in ("NONE", "bid-orion", "BID ORION", "", "X", {"$ne": 1}):
            with self.assertRaises(ValueError):
                e.allow("sub", [bad], [], 1, 1)

    def test_grants_are_sorted_and_unique(self):
        self.assertEqual(decision(["B-2", "A-1", "B-2"]).domains, ("A-1", "B-2"))


class TierSelection(unittest.TestCase):
    def test_no_decision_no_tiers(self):
        self.assertEqual(t.select_tiers(e.refuse("s", e.UNAVAILABLE, "REFUSED_AUTHORIZATION_UNAVAILABLE")), ())

    def test_restricted_tier_only_with_cases(self):
        self.assertEqual(t.select_tiers(decision(["BID-ORION"])), ("shared",))
        self.assertEqual(t.select_tiers(decision([], ["SI-0417"])), ("shared", "restricted"))

    def test_routing(self):
        self.assertEqual([t.tier_for_label(x) for x in ("INTERNAL", "CONFIDENTIAL", "RESTRICTED")],
                         ["shared", "shared", "restricted"])
        with self.assertRaises(ValueError):
            t.tier_for_label("internal")


class Constraints(unittest.TestCase):
    def build(self, d):
        return {q.tier: q for q in constraints.build_tier_queries(d, t.select_tiers(d))}

    def test_zero_domains_single_condition_shape(self):
        self.assertEqual(self.build(decision())["shared"].retrieval_filter,
                         {"equals": {"key": "label", "value": "INTERNAL"}})

    def test_one_domain(self):
        self.assertEqual(self.build(decision(["BID-ORION"]))["shared"].retrieval_filter, {"orAll": [
            {"equals": {"key": "label", "value": "INTERNAL"}},
            {"andAll": [{"equals": {"key": "label", "value": "CONFIDENTIAL"}},
                        {"in": {"key": "scope", "value": ["BID-ORION"]}}]}]})

    def test_many_domains_all_present_in_order(self):
        domains = [f"SYN-DOMAIN-{i:04d}" for i in range(40)]
        value = self.build(decision(domains))["shared"].retrieval_filter["orAll"][1]["andAll"][1]["in"]["value"]
        self.assertEqual(value, sorted(domains))

    def test_restricted_tier_constraint_is_the_assigned_cases_only(self):
        queries = self.build(decision([], ["HR-2031", "SI-0417"]))
        self.assertEqual(queries["restricted"].retrieval_filter, {"andAll": [
            {"equals": {"key": "label", "value": "RESTRICTED"}}, {"in": {"key": "scope", "value": ["HR-2031", "SI-0417"]}}]})
        self.assertEqual(queries["shared"].retrieval_filter, {"equals": {"key": "label", "value": "INTERNAL"}})

    def test_restricted_tier_without_cases_is_refused_never_broadened(self):
        with self.assertRaises(Refusal) as refused:
            constraints.build_tier_queries(decision(["BID-ORION"]), ("shared", "restricted"))
        self.assertEqual(refused.exception.outcome, REFUSED_CONSTRAINT_INCOMPLETE)

    def test_only_positive_operators_are_ever_emitted(self):
        for d in (decision(), decision(["A-1"]), decision(["A-1", "B-2"], ["C-3"])):
            for query in self.build(d).values():
                self.assertLessEqual(operators(query.retrieval_filter) - {"key", "value"}, constraints.ALLOWED_OPERATORS)

    def test_validate_rejects_negative_operators_and_bad_arity(self):
        for bad in ({"notEquals": {"key": "label", "value": "RESTRICTED"}},
                    {"notIn": {"key": "label", "value": ["RESTRICTED"]}},
                    {"orAll": [{"equals": {"key": "label", "value": "INTERNAL"}}]},
                    {"andAll": []},
                    {"equals": {"key": "owner", "value": "x"}},
                    {"in": {"key": "scope", "value": []}},
                    {"equals": {"key": "label", "value": "INTERNAL"}, "in": {"key": "scope", "value": ["A"]}}):
            with self.assertRaises(ValueError):
                constraints.validate(bad)

    def test_over_budget_is_refused_not_truncated(self):
        domains = [f"SYN-OVERLIMIT-{i:04d}" for i in range(999)] + ["FIN-REPORTING"]
        with self.assertRaises(Refusal) as refused:
            constraints.build_tier_queries(decision(domains), ("shared",))
        self.assertEqual(refused.exception.outcome, REFUSED_CONSTRAINT_INCOMPLETE)

    def test_budget_is_below_both_observed_platform_limits(self):
        self.assertEqual(constraints.PLATFORM_OBSERVED_FILTER_LIMIT_BYTES, constraints.VECTOR_STORE_OBSERVED_LIMIT_BYTES)
        self.assertLessEqual(constraints.CONSTRAINT_BUDGET_BYTES, 0.8 * constraints.PLATFORM_OBSERVED_FILTER_LIMIT_BYTES)
        self.assertLess(constraints.CONSTRAINT_BUDGET_BYTES, constraints.RETRIEVE_API_OBSERVED_LIMIT_BYTES)

    def test_largest_accepted_constraint_is_within_budget(self):
        count = 1
        while True:
            try:
                constraints.build_tier_queries(decision([f"SYN-DOMAIN-{i:04d}" for i in range(count + 1)]), ("shared",))
                count += 1
            except Refusal:
                break
        largest = constraints.build_tier_queries(decision([f"SYN-DOMAIN-{i:04d}" for i in range(count)]), ("shared",))[0]
        self.assertLessEqual(largest.filter_bytes, constraints.CONSTRAINT_BUDGET_BYTES)
        self.assertGreater(count, 40)                                   # NFR-002 needs about 40

    def test_deterministic_hash_depends_only_on_the_decision(self):
        a = self.build(decision(["B-2", "A-1"]))["shared"]
        b = self.build(decision(["A-1", "B-2"]))["shared"]
        self.assertEqual(a.filter_sha256, b.filter_sha256)
        self.assertEqual(a.filter_bytes, len(json.dumps(a.retrieval_filter, sort_keys=True)))

    def test_builder_takes_no_question_or_request_input(self):
        self.assertEqual(list(inspect.signature(constraints.build_tier_queries).parameters), ["decision", "tiers"])

    def test_refused_decision_builds_nothing(self):
        with self.assertRaises(Refusal):
            constraints.build_tier_queries(e.refuse("s", e.DENIED, "REFUSED_NO_ACTIVE_EMPLOYMENT"), ("shared",))


if __name__ == "__main__":
    unittest.main()
