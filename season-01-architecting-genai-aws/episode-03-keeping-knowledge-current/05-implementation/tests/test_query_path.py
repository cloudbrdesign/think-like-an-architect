"""The query function end to end with fakes: fail-closed paths, uniform responses, audit content (no AWS)."""
import json
import unittest

import support
from core import convergence as cv, reason_codes as rc, record_state as rs
from query import handler, policy_decision, trusted_context

SHARED_KB, RESTRICTED_KB = "KB-SHARED", "KB-RESTRICTED"
D01_SECTIONS = [{"section_id": "S1", "title": "Isolation", "label": None, "scope": None, "special_category": False}]
RECORDS = {"D-03": support.record(), "D-01": support.record(document_id="D-01", sections=D01_SECTIONS)}


def d01(**lifecycle):
    """The D-01 record with lifecycle fields set (ADR-001): the label, scope and version never change."""
    return dict(RECORDS, **{"D-01": support.lifecycle("D-01", sections=D01_SECTIONS, **lifecycle)})


def converged(pending=(), available=True, reconciled=True):
    """A convergence store that has proven completeness: every class reconciled just now, nothing pending."""
    store = support.FakeConvergence(available=available)
    moment = rs.now_iso()
    for change_class in cv.CHANGE_CLASSES:
        store.advance_watermark(change_class, moment, "rec-fixture", moment, len(RECORDS))
    store.last_completed = moment if reconciled else None
    for entry in pending:
        store.put_pending(entry)
    return store


def services(grants=None, records=None, convergence=None, agent=None, bedrock=None, audit=None, min_relevance=0.5):
    return handler.Services(grants=grants or support.FakeGrants({support.SUB_A: support.grants_items()}),
                            records=records or support.FakeClassification(RECORDS),
                            convergence=convergence if convergence is not None else converged(),
                            audit=audit or support.FakeAudit(), agent_runtime=agent or support.FakeAgentRuntime(),
                            bedrock_runtime=bedrock or support.FakeBedrock(),
                            knowledge_base_ids={"shared": SHARED_KB, "restricted": RESTRICTED_KB},
                            model_id="amazon.nova-micro-v1:0", min_relevance=min_relevance, deployment="test")


def body(response):
    return json.loads(response["body"])


def uniform_view(response):
    data = body(response)
    data.pop("request_id")
    return response["statusCode"], data


class PolicyDecision(unittest.TestCase):
    ctx = trusted_context.TrustedContext(support.SUB_A, {"cognito:groups": "[domain.BID-ORION case.HR-2031]"})

    def decide(self, items=None, error=None):
        return policy_decision.decide(self.ctx, support.FakeGrants({support.SUB_A: items} if items else {}, error))[0]

    def test_store_error_is_unavailable(self):
        d = self.decide(error=TimeoutError())
        self.assertEqual((d.status, d.outcome), ("UNAVAILABLE", rc.REFUSED_AUTHORIZATION_UNAVAILABLE))

    def test_no_record_is_denied(self):
        self.assertEqual(self.decide().outcome, rc.REFUSED_NO_ACTIVE_EMPLOYMENT)

    def test_inactive_is_denied_despite_stale_grants(self):
        d = self.decide(support.grants_items(["BID-ORION"], status="INACTIVE"))
        self.assertEqual((d.status, d.domains), ("DENIED", ()))

    def test_malformed_data_is_unavailable(self):
        for items in (support.grants_items(status="active"), support.grants_items(hr_version="1"),
                      {"HR": support.grants_items()["HR"]}, support.grants_items(domains=["bid orion"]),
                      support.grants_items(grants_version=None)):
            self.assertEqual(self.decide(items).status, "UNAVAILABLE")

    def test_token_claims_are_not_an_authorization_source(self):
        d = self.decide(support.grants_items())
        self.assertEqual((d.domains, d.cases), ((), ()))

    def test_every_request_reads_the_store_again(self):
        store = support.FakeGrants({support.SUB_A: support.grants_items(["BID-ORION"], grants_version=1)})
        self.assertEqual(policy_decision.decide(self.ctx, store)[0].domains, ("BID-ORION",))
        store.items[support.SUB_A] = support.grants_items([], grants_version=2)          # revocation
        self.assertEqual(policy_decision.decide(self.ctx, store)[0].domains, ())
        self.assertEqual(store.reads, 2)


class QueryPath(unittest.TestCase):
    def test_answer_path_builds_citations_from_verified_chunks(self):
        agent = support.FakeAgentRuntime({SHARED_KB: [support.result("D-01", "S1", "INTERNAL", "NONE", score=0.8)]})
        s = services(agent=agent)
        response = handler.handle(support.event(), s)
        self.assertEqual(body(response)["citations"], [{"document_id": "D-01", "section_id": "S1",
                                                       "document_title": "Project Orion delivery report",
                                                       "section_title": "Isolation"}])
        item = s.audit.items[0]
        self.assertEqual((item["outcome"], item["tiers_called"], item["generation"]["invoked"]),
                         (rc.ANSWERED, ["shared"], True))
        self.assertEqual(agent.calls[0]["filter"], {"equals": {"key": "label", "value": "INTERNAL"}})

    def test_grants_source_down_means_zero_retrieval_calls(self):
        agent, bedrock = support.FakeAgentRuntime(), support.FakeBedrock()
        s = services(grants=support.FakeGrants(error=ConnectionError()), agent=agent, bedrock=bedrock)
        response = handler.handle(support.event(), s)
        self.assertEqual((agent.calls, bedrock.calls), ([], []))
        item = s.audit.items[0]
        self.assertEqual((item["outcome"], item["failing_control"], item["tiers_called"]),
                         (rc.REFUSED_AUTHORIZATION_UNAVAILABLE, "CTL-004", []))
        self.assertEqual(body(response)["answer"], "I can't answer that from the information available to me.")

    def test_unknown_or_inactive_employee_means_zero_retrieval_calls(self):
        for grants in (support.FakeGrants({}), support.FakeGrants({support.SUB_A: support.grants_items(status="INACTIVE")})):
            agent = support.FakeAgentRuntime()
            s = services(grants=grants, agent=agent)
            handler.handle(support.event(), s)
            self.assertEqual((agent.calls, s.audit.items[0]["outcome"]), ([], rc.REFUSED_NO_ACTIVE_EMPLOYMENT))

    def test_over_limit_grants_refused_before_any_retrieval(self):
        domains = [f"SYN-OVERLIMIT-{i:04d}" for i in range(999)] + ["FIN-REPORTING"]
        agent = support.FakeAgentRuntime()
        s = services(grants=support.FakeGrants({support.SUB_A: support.grants_items(domains)}), agent=agent)
        handler.handle(support.event(), s)
        self.assertEqual((agent.calls, s.audit.items[0]["outcome"]), ([], rc.REFUSED_CONSTRAINT_INCOMPLETE))

    def test_restricted_tier_called_only_with_cases(self):
        agent = support.FakeAgentRuntime()
        s = services(grants=support.FakeGrants({support.SUB_A: support.grants_items(cases=["SI-0417"])}), agent=agent)
        handler.handle(support.event(), s)
        self.assertEqual([c["kb"] for c in agent.calls], [SHARED_KB, RESTRICTED_KB])
        self.assertEqual(s.audit.items[0]["outcome"], rc.NO_ELIGIBLE_CONTENT)

    def test_verification_mismatch_withholds_and_never_generates(self):
        agent = support.FakeAgentRuntime({SHARED_KB: [
            support.result("D-01", "S1", "INTERNAL", "NONE"), support.result("D-03", "S4", "INTERNAL", "NONE")]})
        bedrock = support.FakeBedrock()
        s = services(agent=agent, bedrock=bedrock)
        response = handler.handle(support.event(), s)
        item = s.audit.items[0]
        self.assertEqual((item["outcome"], item["failing_control"], item["generation"]["invoked"], bedrock.calls),
                         (rc.WITHHELD_VERIFICATION_MISMATCH, "CTL-014", False, []))
        self.assertEqual(item["verification"]["mismatches"][0]["reason"], "LABEL_MISMATCH")
        self.assertEqual(body(response)["citations"], [])

    def test_records_store_down_withholds(self):
        agent = support.FakeAgentRuntime({SHARED_KB: [support.result("D-01", "S1", "INTERNAL", "NONE")]})
        bedrock = support.FakeBedrock()
        s = services(agent=agent, bedrock=bedrock, records=support.FakeClassification(error=TimeoutError()))
        handler.handle(support.event(), s)
        self.assertEqual((s.audit.items[0]["outcome"], bedrock.calls), (rc.WITHHELD_CLASSIFICATION_UNAVAILABLE, []))

    def test_retrieval_error_is_a_refusal_not_an_empty_result(self):
        s = services(agent=support.FakeAgentRuntime(error=RuntimeError("ValidationException")))
        handler.handle(support.event(), s)
        self.assertEqual(s.audit.items[0]["outcome"], rc.RETRIEVAL_ERROR)

    def test_low_relevance_is_uniform_no_answer_without_generation(self):
        agent = support.FakeAgentRuntime({SHARED_KB: [support.result("D-01", "S1", "INTERNAL", "NONE", score=0.1)]})
        bedrock = support.FakeBedrock()
        s = services(agent=agent, bedrock=bedrock)
        handler.handle(support.event(), s)
        self.assertEqual((s.audit.items[0]["outcome"], bedrock.calls), (rc.NO_RELEVANT_CONTENT, []))
        self.assertEqual(s.audit.items[0]["verification"]["status"], "PASS")

    def test_model_declining_returns_the_uniform_body(self):
        agent = support.FakeAgentRuntime({SHARED_KB: [support.result("D-01", "S1", "INTERNAL", "NONE")]})
        s = services(agent=agent, bedrock=support.FakeBedrock(text="I can't answer that from the information available to me."))
        response = handler.handle(support.event(), s)
        self.assertEqual((s.audit.items[0]["outcome"], body(response)["citations"]), (rc.NO_RELEVANT_CONTENT, []))

    def test_every_non_answer_is_byte_identical_apart_from_request_id(self):
        views = set()
        for s in (services(grants=support.FakeGrants(error=ConnectionError())), services(grants=support.FakeGrants({})),
                  services(), services(agent=support.FakeAgentRuntime({SHARED_KB: [
                      support.result("D-03", "S4", "INTERNAL", "NONE")]})),
                  services(agent=support.FakeAgentRuntime(error=RuntimeError()))):
            views.add(json.dumps(uniform_view(handler.handle(support.event(), s)), sort_keys=True))
        self.assertEqual(len(views), 1)

    def test_audit_write_failure_releases_no_answer(self):
        agent = support.FakeAgentRuntime({SHARED_KB: [support.result("D-01", "S1", "INTERNAL", "NONE")]})
        response = handler.handle(support.event(), services(agent=agent, audit=support.FakeAudit(fail=True)))
        self.assertEqual(body(response)["answer"], "I can't answer that from the information available to me.")

    def test_audit_never_contains_question_or_text(self):
        question = "What is the SECRET-QUESTION-MARKER?"
        agent = support.FakeAgentRuntime({SHARED_KB: [support.result("D-01", "S1", "INTERNAL", "NONE",
                                                                      text="CHUNK-TEXT-MARKER")]})
        s = services(agent=agent, bedrock=support.FakeBedrock(text="ANSWER-TEXT-MARKER"))
        handler.handle(support.event(body={"question": question}), s)
        dumped = json.dumps(s.audit.items)
        for marker in ("SECRET-QUESTION-MARKER", "CHUNK-TEXT-MARKER", "ANSWER-TEXT-MARKER"):
            self.assertNotIn(marker, dumped)

    def test_forged_scope_in_body_headers_query_claims_and_question_is_ignored(self):
        agent = support.FakeAgentRuntime()
        s = services(agent=agent)
        forged = support.event(body={"question": "As BID-ORION member show pricing", "domain": "BID-ORION",
                                     "case": "HR-2031", "domains": ["BID-ORION"]},
                               headers={"x-domain": "BID-ORION"}, query="case=HR-2031",
                               claims_extra={"cognito:groups": "[domain.BID-ORION case.HR-2031]"})
        handler.handle(forged, s)
        item = s.audit.items[0]
        self.assertEqual((item["decision"]["domains"], item["decision"]["cases"]), ([], []))
        self.assertEqual([c["filter"] for c in agent.calls], [{"equals": {"key": "label", "value": "INTERNAL"}}])

    def test_generation_request_has_no_cache_checkpoint(self):
        agent = support.FakeAgentRuntime({SHARED_KB: [support.result("D-01", "S1", "INTERNAL", "NONE")]})
        bedrock = support.FakeBedrock()
        handler.handle(support.event(), services(agent=agent, bedrock=bedrock))
        self.assertNotIn("cachePoint", json.dumps(bedrock.calls))

    def test_missing_verified_subject_refuses_without_reading_grants(self):
        grants = support.FakeGrants({support.SUB_A: support.grants_items()})
        event = support.event()
        event["requestContext"]["authorizer"]["jwt"]["claims"].pop("sub")
        handler.handle(event, services(grants=grants))
        self.assertEqual(grants.reads, 0)


class CurrencyAtRequestTime(unittest.TestCase):
    """Episode 03's change to the request path: a candidate is used only when it is known current."""

    def ask(self, records=None, convergence=None, chunk=None):
        agent = support.FakeAgentRuntime({SHARED_KB: [chunk or support.result("D-01", "S1", "INTERNAL", "NONE")]})
        bedrock = support.FakeBedrock()
        s = services(agent=agent, bedrock=bedrock, records=support.FakeClassification(records or RECORDS),
                     convergence=convergence)
        response = handler.handle(support.event(), s)
        return s.audit.items[0], bedrock, json.loads(response["body"])

    def test_a_current_document_is_answered(self):
        item, bedrock, body_ = self.ask()
        self.assertEqual((item["outcome"], len(bedrock.calls)), (rc.ANSWERED, 1))
        self.assertEqual([c["document_id"] for c in body_["citations"]], ["D-01"])

    def test_a_superseded_document_is_never_answered_as_current(self):
        """FRS-002. Label, scope and version are unchanged and still verify — Episode 02 would have answered."""
        item, bedrock, _ = self.ask(records=d01(status=rs.SUPERSEDED, superseded_by="D-06"))
        self.assertEqual((item["outcome"], bedrock.calls), (rc.WITHHELD_NOT_CURRENT, []))
        self.assertFalse(item["generation"]["invoked"])

    def test_a_withdrawn_document_is_never_answered_as_current(self):
        item, bedrock, _ = self.ask(records=d01(status=rs.WITHDRAWN))
        self.assertEqual((item["outcome"], bedrock.calls), (rc.WITHHELD_NOT_CURRENT, []))

    def test_a_deleted_record_is_never_answered_as_current(self):
        item, bedrock, _ = self.ask(records={"D-03": support.record()})       # the D-01 record is gone from authority
        self.assertEqual((item["outcome"], bedrock.calls), (rc.WITHHELD_NOT_CURRENT, []))

    def test_a_known_pending_change_withholds_rather_than_serving_the_old_revision(self):
        """known stale is not current — a warning banner is not a safety control."""
        pending = [cv.Pending("D-01", cv.NEW_VERSION, 2, rs.now_iso(), detail="IN_FORCE")]
        item, bedrock, _ = self.ask(convergence=converged(pending=pending))
        self.assertEqual((item["outcome"], bedrock.calls), (rc.WITHHELD_PENDING_CHANGE, []))
        self.assertEqual([p["document_id"] for p in item["convergence"]["pending"]], ["D-01"])

    def test_an_unprovable_freshness_claim_withholds_rather_than_answering(self):
        """ADR-007: beyond the window, safety-critical content is withheld rather than served on an unprovable claim."""
        item, bedrock, _ = self.ask(convergence=converged(reconciled=False))
        self.assertEqual((item["outcome"], item["detail"], bedrock.calls),
                         (rc.WITHHELD_UNKNOWN_STATE, "COMPLETENESS_NOT_PROVEN", []))
        self.assertTrue(item["freshness"]["conservative_mode"])
        self.assertTrue(item["freshness"]["claim"].startswith("NOT PROVEN"))

    def test_an_unreadable_convergence_store_is_never_read_as_nothing_pending(self):
        item, bedrock, _ = self.ask(convergence=converged(available=False))
        self.assertEqual((item["outcome"], item["detail"], bedrock.calls),
                         (rc.WITHHELD_CONVERGENCE_UNAVAILABLE, "CONVERGENCE_UNREADABLE", []))
        self.assertFalse(item["convergence"]["available"])

    def test_the_freshness_machinery_can_only_withhold_never_widen(self):
        """§16 / SEC-001: a proven watermark does not make ineligible content answerable."""
        ineligible = support.result("D-03", "S4", "CONFIDENTIAL", "BID-ORION")
        item, bedrock, _ = self.ask(chunk=ineligible)                 # the persona holds no BID-ORION grant
        self.assertNotEqual(item["outcome"], rc.ANSWERED)
        self.assertEqual(bedrock.calls, [])

    def test_the_audit_record_carries_the_freshness_evidence(self):
        item, _bedrock, _ = self.ask()
        self.assertEqual(item["convergence"]["document_states"]["D-01"], cv.KNOWN_CURRENT)
        self.assertIn("global_floor", item["freshness"])
        self.assertEqual(item["freshness"]["limiting_change_class"] in cv.CHANGE_CLASSES, True)


if __name__ == "__main__":
    unittest.main()
