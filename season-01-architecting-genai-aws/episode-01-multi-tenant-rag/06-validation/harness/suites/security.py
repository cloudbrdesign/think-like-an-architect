"""Security tests: TST-SEC-006 prompt attack, TST-SEC-008 indirect injection, TST-SEC-021 citation isolation,
TST-SEC-022 divergence detection, TST-SEC-009 bypass paths."""
import json
import time

from harness.common import fixture_text
from harness.context import audit_view

SUITE = "security"
CITATION_KEYS = ["document_id", "label", "location", "title"]
FORBIDDEN_IN_CITATIONS = ("s3://", "tenants/", "x-amz", "arn:", "score", "owning_tenant")


def run(ctx):
    prompt_attack(ctx)
    indirect_injection(ctx)
    citations(ctx)
    divergence(ctx)
    bypass(ctx)


def prompt_attack(ctx):
    baseline_response, baseline = ctx.ask("user-a", ctx.q["own_topic"])
    response, record = ctx.ask("user-a", ctx.q["prompt_attack"])
    findings = ctx.leak_findings("tenant-a", response, record)
    same = bool(record and baseline and record.get("constraint_sha256") == baseline.get("constraint_sha256"))
    ok = response.status == 200 and same and not ctx.is_leak(findings)
    ctx.run.record("TST-SEC-006", SUITE, ["SEC-005"], ["CTL-016", "CTL-015"], "L3",
                   "Constraint identical to a normal Tenant A request; no Tenant B document retrieved",
                   "PASS" if ok else "FAIL",
                   "constraint hash identical to baseline; no foreign retrieval" if ok else f"constraint_same={same}, findings={findings}",
                   {"baseline": audit_view(baseline), "attack_response": response.summary(),
                    "attack_answer": (response.body or {}).get("answer"), "attack_audit": audit_view(record), "findings": findings})


def indirect_injection(ctx):
    response, record = ctx.ask("user-a", ctx.q["indirect_injection"])
    ctx.responses["TST-SEC-008"] = (response, record, "tenant-a")
    findings = ctx.leak_findings("tenant-a", response, record)
    records = ctx.obs.audit_for_request(response.request_id) if response.request_id else []
    hostile_retrieved = ctx.doc("A4") in [r["document_id"] for r in (record or {}).get("retrieved", [])]
    ok = (response.status == 200 and record and record["constraint"]["value"] == "tenant-a" and len(records) == 1
          and not ctx.is_leak(findings))
    ctx.run.record("TST-SEC-008", SUITE, ["SEC-005"], ["CTL-016", "CTL-022", "CTL-018"], "L3",
                   "One retrieval with the Tenant A constraint; no foreign identifiers, markers or citations",
                   "PASS" if ok else "FAIL",
                   (f"single retrieval under tenant-a; hostile document retrieved={hostile_retrieved}; no foreign content"
                    if ok else f"records={len(records)}, findings={findings}"),
                   {"response": response.summary(), "answer": (response.body or {}).get("answer"),
                    "citations": (response.body or {}).get("citations"), "audit": audit_view(record),
                    "audit_records_for_request": len(records), "hostile_document_retrieved": hostile_retrieved,
                    "findings": findings})


def citations(ctx):
    fabricated_response, fabricated_record = ctx.ask("user-a", ctx.q["citation_fabrication"])
    samples = [("fabrication", fabricated_response, fabricated_record, "tenant-a")]
    for key in ("TST-ISO-001", "TST-ISO-002", "TST-SEC-008"):
        if key in ctx.responses:
            samples.append((key, *ctx.responses[key]))
    for response, record, tenant in ctx.responses.get("negative:user-a", [])[:3]:
        samples.append(("TST-ISO-003", response, record, tenant))
    titles = {t: {d["title"] for d in ctx.state["documents"].values() if d["tenant"] == t and not d.get("removed")}
              for t in ("tenant-a", "tenant-b")}
    problems, observations = [], []
    for name, response, record, tenant in samples:
        cited = (response.body or {}).get("citations", []) if isinstance(response.body, dict) else []
        own, verified = ctx.own(tenant), {r["document_id"] for r in (record or {}).get("retrieved", [])}
        text = json.dumps(cited)
        issues = []
        for c in cited:
            if sorted(c) != CITATION_KEYS:
                issues.append(f"fields {sorted(c)}")
            if c.get("document_id") not in own or c.get("location") != f"/documents/{c.get('document_id')}":
                issues.append("foreign or malformed citation")
            if c.get("title") not in titles[tenant]:
                issues.append(f"title not an own title: {c.get('title')}")
        issues += [f"forbidden '{f}'" for f in FORBIDDEN_IN_CITATIONS if f in text]
        if record and not set(record.get("cited_document_ids") or []) <= verified:
            issues.append("cited ⊄ retrieved-and-verified")
        observations.append({"sample": name, "status": response.status, "citations": cited,
                             "cited_document_ids": (record or {}).get("cited_document_ids"), "issues": issues})
        problems += [f"{name}: {i}" for i in issues]
    ctx.run.record("TST-SEC-021", SUITE, ["SEC-001", "FUN-001"], ["CTL-018"], "L3",
                   "Citations contain only own document ID, title and route location; cited ⊆ verified; fabricated reference removed",
                   "FAIL" if problems else "PASS", "; ".join(problems[:5]) or
                   f"{sum(len(o['citations']) for o in observations)} citations across {len(observations)} responses, all allow-listed and own",
                   {"samples": observations, "fabrication_answer": (fabricated_response.body or {}).get("answer")})


def divergence(ctx):
    """TST-SEC-022 — the operator deliberately bypasses the attribution gate in the sandbox, then removes the fixture."""
    fixture = ctx.data["edge_cases"]["E4"]
    out, agent = ctx.target.outputs, ctx.target.client("bedrock-agent")
    doc_id = fixture["document_id"]
    observations, status, reason = {}, "ERROR", "fixture not created"
    try:
        ctx.obs.registry_put({"pk": f"DOC#{doc_id}", "item_type": "DOCUMENT", "document_id": doc_id,
                              "owner": fixture["record_owner"], "uploader": "operator-fixture", "title": fixture["title"],
                              "s3_key": "none", "status": "AVAILABLE", "created_at": "fixture"})
        agent.ingest_knowledge_base_documents(
            knowledgeBaseId=out["KnowledgeBaseId"], dataSourceId=out["DataSourceId"],
            documents=[{"content": {"dataSourceType": "CUSTOM", "custom": {
                "customDocumentIdentifier": {"id": doc_id}, "sourceType": "IN_LINE",
                "inlineContent": {"type": "TEXT", "textContent": {"data": fixture_text(fixture["file"])}}}},
                "metadata": {"type": "IN_LINE_ATTRIBUTE", "inlineAttributes": [
                    {"key": "owning_tenant", "value": {"type": "STRING", "stringValue": fixture["attribute_owner"]}},
                    {"key": "document_id", "value": {"type": "STRING", "stringValue": doc_id}}]}}])
        deadline = time.time() + 240
        while time.time() < deadline and ctx.obs.index_status(doc_id) != "INDEXED":
            time.sleep(5)
        observations["fixture_index_status"] = ctx.obs.index_status(doc_id)
        response, record = ctx.ask("user-b", ctx.q["divergence"])
        body = response.body if isinstance(response.body, dict) else {}
        retrieved_ids = [r["document_id"] for r in (record or {}).get("retrieved", [])]
        observations.update({"response": response.summary(), "response_body": body, "audit": audit_view(record)})
        ok = (response.code() == "OWNERSHIP_MISMATCH" and record and record["verification_outcome"] == "OWNERSHIP_MISMATCH"
              and doc_id in retrieved_ids and "answer" not in body and "citations" not in body
              and "AMBER-FALCON" not in json.dumps(body))
        status = "PASS" if ok else ("ERROR" if doc_id not in retrieved_ids else "FAIL")
        reason = ("divergent chunk retrieved under tenant-b; response withheld; OWNERSHIP_MISMATCH recorded" if ok else
                  "fixture was not retrieved (inconclusive)" if doc_id not in retrieved_ids else "divergence not withheld")
    finally:
        try:
            agent.delete_knowledge_base_documents(knowledgeBaseId=out["KnowledgeBaseId"], dataSourceId=out["DataSourceId"],
                                                  documentIdentifiers=[{"dataSourceType": "CUSTOM", "custom": {"id": doc_id}}])
        except Exception as error:  # noqa: BLE001
            observations["fixture_removal_error"] = type(error).__name__
        ctx.obs.registry_delete(f"DOC#{doc_id}")
        deadline = time.time() + 180
        while time.time() < deadline and ctx.obs.index_status(doc_id) not in ("NOT_FOUND",):
            time.sleep(5)
        observations["fixture_removed"] = {"index_status": ctx.obs.index_status(doc_id),
                                           "ownership_record": ctx.obs.registry_get(f"DOC#{doc_id}")}
    ctx.run.record("TST-SEC-022", SUITE, ["DATA-003", "SEC-001"], ["CTL-017"], "L4",
                   "DETECTED: entire response withheld; verification_outcome OWNERSHIP_MISMATCH; nothing generated",
                   status, reason, observations, privileged=True)


def bypass(ctx):
    t, out = ctx.target, ctx.target.outputs
    cases, problems = {}, []
    forged = {"routeKey": "POST /ask", "body": json.dumps({"question": ctx.q["own_topic"]}),
              "requestContext": {"requestId": "forged", "authorizer": {"jwt": {"claims": {
                  "sub": "forged", "token_use": "access", "client_id": out["AppClientId"], "iss": out["TokenIssuer"],
                  "cognito:groups": "[tenant-b]"}}}}}
    try:
        t.client("lambda").invoke(FunctionName=out["QueryFunctionName"], Payload=json.dumps(forged).encode())
        cases["1 direct invocation with forged claims"] = "INVOKED"
        problems.append("direct invocation succeeded")
    except Exception as error:  # noqa: BLE001
        cases["1 direct invocation with forged claims"] = f"{type(error).__name__}: {str(error)[-90:]}"
    iam = t.client("iam")
    simulations = {name: iam.simulate_principal_policy(PolicySourceArn=out[arn], ActionNames=["bedrock:Retrieve"],
                                                       ResourceArns=[out["KnowledgeBaseArn"]])["EvaluationResults"][0]["EvalDecision"]
                   for name, arn in (("IngestionRole", "IngestionRoleArn"), ("KnowledgeBaseServiceRole", "KnowledgeBaseServiceRoleArn"))}
    resources = t.client("cloudformation").describe_stack_resources(StackName=t.stack_name)["StackResources"]
    cases["2 retrieval with other credentials"] = {
        "other_application_roles": simulations,
        "end_users_have_aws_credentials": any(r["ResourceType"] == "AWS::Cognito::IdentityPool" for r in resources)}
    if any(v == "allowed" for v in simulations.values()) or cases["2 retrieval with other credentials"]["end_users_have_aws_credentials"]:
        problems.append("retrieval available to another principal")
    record = ctx.obs.registry_get(f"DOC#{ctx.doc('A1')}")
    try:
        t.client("s3").get_object(Bucket=out["DocumentBucket"], Key=record["s3_key"])
        cases["3 direct read of an original"] = "READ"
        problems.append("original readable directly")
    except Exception as error:  # noqa: BLE001
        cases["3 direct read of an original"] = type(error).__name__ + (": " + error.response["Error"]["Code"] if hasattr(error, "response") else "")
    reply = ctx.api.call("GET", f"/documents/{ctx.doc('A1')}", token=ctx.ids.access("user-b"))
    cases["4 open another tenant's document by ID"] = reply.summary()
    if reply.status != 404:
        problems.append("cross-tenant open did not return not-found")
    probes = {}
    token = ctx.ids.access("user-a")
    for label, kwargs in {
        "debug body field": {"body": {"question": ctx.q["own_topic"], "debug": True}},
        "debug and tenant=all query": {"body": {"question": ctx.q["own_topic"]}, "query": "debug=true&tenant=all&filter=none"},
        "debug header": {"body": {"question": ctx.q["own_topic"]}, "headers": {"X-Debug": "1", "X-Disable-Isolation": "true"}},
    }.items():
        reply = ctx.api.call("POST", "/ask", token=token, **kwargs)
        audit = ctx.obs.audit(reply.event_id) if reply.event_id else None
        probes[label] = {"response": reply.summary(), "constraint": (audit or {}).get("constraint")}
        if reply.status == 200 and (audit or {}).get("constraint", {}).get("value") != "tenant-a":
            problems.append(f"{label} changed the constraint")
    for path in ("/debug", "/admin", "/documents"):
        reply = ctx.api.call("GET", path, token=token)
        probes[f"GET {path}"] = reply.summary()
        if reply.status != 404:
            problems.append(f"GET {path} exists")
    cases["5 debug or override parameters"] = probes
    cases["6 legacy export role"] = "NOT_APPLICABLE — not part of the learner build"
    ctx.run.record("TST-SEC-009", SUITE, ["SEC-009"], ["CTL-008", "CTL-009", "CTL-014"], "L3+L1",
                   "BLOCKED in every case, or the path does not exist for tenant users",
                   "FAIL" if problems else "PASS", "; ".join(problems) or
                   "direct invoke denied by explicit Deny; no other retrieval principal; originals unreadable directly; "
                   "cross-tenant open not found; no debug or override path", cases, privileged=True)
