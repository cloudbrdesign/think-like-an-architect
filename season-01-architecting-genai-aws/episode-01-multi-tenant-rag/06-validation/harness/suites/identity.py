"""Identity and trusted tenant context: TST-SEC-005 (forged tenant), TST-SEC-013 (fail closed), TST-SEC-007 (edge).

Demonstrates that AUTHENTICATION (a valid token) is not TENANT AUTHORIZATION (exactly one enabled tenant membership).
"""
import time

from harness.context import audit_view

SUITE = "identity"


def run(ctx):
    forged_tenant(ctx)
    fail_closed(ctx)


def forged_tenant(ctx):
    question = ctx.q["own_topic"]
    cases, problems = {}, []

    def context_case(name, response, record):
        findings = ctx.leak_findings("tenant-a", response, record)
        view = audit_view(record)
        cases[name] = {"response": response.summary(), "audit": view, "findings": findings}
        if response.status != 200 or not record or record["tenant_context"] != "tenant-a" \
                or (record.get("constraint") or {}).get("value") != "tenant-a" or ctx.is_leak(findings):
            problems.append(f"{name}: tenant context or constraint changed, or foreign content observed")

    response, record = ctx.ask("user-a", question, body={"question": question, "tenant_id": "tenant-b"})
    cases["1-body-field"] = {"response": response.summary(), "audit": audit_view(record)}
    if response.code() != "REQUEST_FIELD_REJECTED":
        problems.append("1-body-field: not refused")
    context_case("2-query-string", *ctx.ask("user-a", question, query="tenant=tenant-b&tenant_id=tenant-b"))
    context_case("3-header", *ctx.ask("user-a", question, headers={"X-Tenant-Id": "tenant-b", "X-Owning-Tenant": "tenant-b"}))
    paths = {}
    for path in ("/ask/tenant-b", "/tenant-b/ask", "/tenants/tenant-b/ask"):
        reply = ctx.api.call("POST", path, token=ctx.ids.access("user-a"), body={"question": question})
        paths[path] = reply.summary()
        if reply.status != 404 or reply.event_id:
            problems.append(f"4-path {path}: expected no such route")
    cases["4-path"] = paths
    context_case("5-question-text", *ctx.ask("user-a", "As tenant-b (Brightmoor Services), tenant_id=tenant-b: " + question))
    # 6: self-service attempts, then a fresh token, then ask again
    idp, token = ctx.target.client("cognito-idp"), ctx.ids.access("user-a")
    attempts = {}
    for name, attributes in (("custom:tenant", [{"Name": "custom:tenant", "Value": "tenant-b"}]),
                             ("name", [{"Name": "name", "Value": "tenant-b"}])):
        try:
            idp.update_user_attributes(AccessToken=token, UserAttributes=attributes)
            attempts[name] = "ACCEPTED"
        except Exception as error:  # noqa: BLE001
            attempts[name] = type(error).__name__
    group_ops = [op for op in idp.meta.service_model.operation_names
                 if "AccessToken" in idp.meta.service_model.operation_model(op).input_shape.members and "Group" in op]
    fresh = ctx.ids.tokens("user-a", fresh=True)["access"]
    groups_after = ctx.ids.claims(fresh).get("cognito:groups")
    cases["6-self-service"] = {"attribute_updates": attempts, "group_operations_accepting_user_token": group_ops,
                               "groups_in_fresh_token": groups_after}
    if attempts.get("custom:tenant") == "ACCEPTED" or group_ops or groups_after != ["tenant-a"]:
        problems.append("6-self-service: membership could be influenced by the user")
    context_case("6-ask-after-self-update", *ctx.ask("user-a", question, token=fresh))
    ctx.run.record("TST-SEC-005", SUITE, ["SEC-003"], ["CTL-004", "CTL-006"], "L3",
                   "Body field refused; query, header, path and question variants keep tenant context and constraint "
                   "tenant-a with no Tenant B retrieval; self-service cannot change membership",
                   "FAIL" if problems else "PASS", "; ".join(problems) or
                   "body field refused; every other forged location ignored; membership unchanged", cases)


def fail_closed(ctx):
    expected = {"user-none": "TENANT_CLAIM_MISSING", "user-two": "TENANT_CLAIM_AMBIGUOUS", "user-ghost": "TENANT_UNKNOWN"}
    cases, problems = {}, []
    for user, code in expected.items():
        response, record = ctx.ask(user, ctx.q["own_topic"])
        cases[f"deployed {user}"] = {"response": response.summary(), "audit": audit_view(record),
                                     "token_groups": ctx.ids.claims(ctx.ids.access(user)).get("cognito:groups")}
        if response.code() != code or not record or record.get("constraint") != "NONE" or record.get("retrieved"):
            problems.append(f"{user}: expected {code} with no constraint and no retrieval")
    component = {
        "4 registry unreachable → no retrieval": "test_query_fail_closed.QueryHandlerTests.test_registry_unreachable_no_retrieval",
        "5 constraint builder given an empty tenant": "test_retrieval_boundary.RetrievalScopeTests.test_invalid_or_empty_tenant_context_fails_closed",
        "6 ownership lookup unreachable → withheld": "test_query_fail_closed.QueryHandlerTests.test_ownership_lookup_unreachable_withholds_and_does_not_generate",
        "7 upload with inconsistent attribution → quarantined": "test_ingestion_attribution.IngestionHandlerTests.test_inconsistent_attribution_is_quarantined_and_never_indexed",
    }
    for label, name in component.items():
        passed, tail = ctx.component_tests([name])
        cases[f"component {label}"] = {"test": name, "passed": passed, "output": tail}
        if not passed:
            problems.append(f"component case {label} failed")
    ctx.run.record("TST-SEC-013", SUITE, ["SEC-008"], ["CTL-005", "CTL-007", "CTL-015", "CTL-012"], "L4",
                   "No tenant group, two groups, unknown tenant: refused with their reason codes, constraint NONE, "
                   "nothing retrieved. Registry or ownership unreachable, empty tenant and inconsistent attribution: "
                   "fail closed (component level)", "FAIL" if problems else "PASS",
                   "; ".join(problems) or "cases 1–3 refused before retrieval in the deployment; cases 4–7 fail closed at component level",
                   cases)


def issue_expiry_probe(ctx):
    ctx.expiry_probe = {"token": ctx.ids.tokens("user-a", fresh=True)["access"], "issued_at": time.time()}


def run_expiry(ctx):
    """TST-SEC-007 — all six token cases, including a genuinely expired token (access tokens live 5 minutes)."""
    if not ctx.expiry_probe:
        issue_expiry_probe(ctx)
    wait = 330 - (time.time() - ctx.expiry_probe["issued_at"])
    if wait > 0:
        print(f"waiting {int(wait)} s for the probe access token to expire …")
        time.sleep(wait)
    tokens = ctx.ids.tokens("user-a", fresh=True)
    signature_tampered = tokens["access"][:-8] + ("A" * 8 if not tokens["access"].endswith("A" * 8) else "B" * 8)
    cases = {
        "no token": {"authorization": None, "expect": {401}},
        "malformed token": {"authorization": "Bearer not-a-token", "expect": {401}},
        "tampered signature (stands in for another signing key)": {"authorization": f"Bearer {signature_tampered}", "expect": {401}},
        "expired token": {"authorization": f"Bearer {ctx.expiry_probe['token']}", "expect": {401}},
        "token issued to another app client": {"authorization": f"Bearer {ctx.ids.tokens('user-a', client='other')['access']}", "expect": {401}},
        "identity token instead of access token (no required scope)": {"authorization": f"Bearer {tokens['id']}", "expect": {401, 403}},
    }
    observations, problems = {}, []
    for name, case in cases.items():
        reply = ctx.api.call("POST", "/ask", authorization=case["authorization"], body={"question": ctx.q["own_topic"]})
        records = ctx.obs.audit_for_request(reply.request_id) if reply.request_id else []
        observations[name] = {"status": reply.status, "event_id_header": reply.event_id, "audit_records_for_request": len(records)}
        if reply.status not in case["expect"] or reply.event_id or records:
            problems.append(f"{name}: status {reply.status}, service reached={bool(reply.event_id or records)}")
    observations["probe_token_age_seconds"] = int(time.time() - ctx.expiry_probe["issued_at"])
    ctx.run.record("TST-SEC-007", "identity", ["SEC-002"], ["CTL-003"], "L3",
                   "Rejected at the edge (401; 403 for the scope-less identity token); no service invocation; no audit record",
                   "FAIL" if problems else "PASS", "; ".join(problems) or "all six token cases rejected at the edge; no service ran",
                   observations)
