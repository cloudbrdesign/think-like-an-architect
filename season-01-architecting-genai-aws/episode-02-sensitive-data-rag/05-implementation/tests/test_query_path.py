"""The query function end to end with fakes: fail-closed paths, uniform responses, audit content (no AWS)."""
import json
import unittest

import support
from core import reason_codes as rc
from query import handler, policy_decision, trusted_context

SHARED_KB, RESTRICTED_KB = "KB-SHARED", "KB-RESTRICTED"
RECORDS = {"D-03": support.record(),
           "D-01": support.record(document_id="D-01", sections=[
               {"section_id": "S1", "title": "Isolation", "label": None, "scope": None, "special_category": False}])}


def services(grants=None, classification=None, agent=None, bedrock=None, audit=None, min_relevance=0.5):
    return handler.Services(grants=grants or support.FakeGrants({support.SUB_A: support.grants_items()}),
                            classification=classification or support.FakeClassification(RECORDS),
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

    def test_classification_store_down_withholds(self):
        agent = support.FakeAgentRuntime({SHARED_KB: [support.result("D-01", "S1", "INTERNAL", "NONE")]})
        bedrock = support.FakeBedrock()
        s = services(agent=agent, bedrock=bedrock, classification=support.FakeClassification(error=TimeoutError()))
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


if __name__ == "__main__":
    unittest.main()
