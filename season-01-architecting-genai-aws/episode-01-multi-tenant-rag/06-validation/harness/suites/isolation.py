"""Tenant isolation, observed at the retrieval layer: TST-ISO-001 … TST-ISO-004 (CTL-015 primary; CTL-017, CTL-018).

A negative test is only meaningful if the other tenant's target document exists and ranks for the same question under
that tenant's own constraint. That non-vacuity precondition is checked first (privileged operator retrieval); if it does
not hold, the test is ERROR — vacuous, never PASS.
"""
from harness.context import audit_view

SUITE = "isolation"


def run(ctx):
    positive(ctx, "TST-ISO-001", "user-a", "tenant-a")
    positive(ctx, "TST-ISO-002", "user-b", "tenant-b")
    run_negative(ctx)


def run_negative(ctx, suite=SUITE):
    record_negative(ctx, "TST-ISO-003", "user-a", "tenant-a", "tenant-b", ctx.q["cross_tenant_a_to_b"], suite)
    record_negative(ctx, "TST-ISO-004", "user-b", "tenant-b", "tenant-a", ctx.q["cross_tenant_b_to_a"], suite)


def positive(ctx, test_id, user, tenant):
    response, record = ctx.ask(user, ctx.q["own_topic"])
    ctx.responses[test_id] = (response, record, tenant)
    own = ctx.own(tenant)
    retrieved = (record or {}).get("retrieved") or []
    citations = (response.body or {}).get("citations", []) if isinstance(response.body, dict) else []
    problems = []
    if response.status != 200:
        problems.append(f"status {response.status} {response.code()}")
    if not retrieved:
        problems.append("nothing retrieved")
    if any(r["owner_attribute"] != tenant or r["document_id"] not in own for r in retrieved):
        problems.append("retrieved a document not owned by the tenant")
    if not citations or any(c["document_id"] not in own for c in citations):
        problems.append("no citation of an own document")
    ctx.run.record(test_id, SUITE, ["FUN-001", "FUN-002"], ["CTL-004", "CTL-011", "CTL-015", "CTL-018"], "L3",
                   f"ALLOWED: {tenant} retrieves and cites only its own documents", "FAIL" if problems else "PASS",
                   "; ".join(problems) or f"{len(retrieved)} chunks retrieved, all {tenant}; cited {len(citations)} own document(s)",
                   {"response": response.summary(), "answer": (response.body or {}).get("answer"), "citations": citations,
                    "audit": audit_view(record)})


def negative(ctx, user, own_tenant, other_tenant, questions):
    """Return (status, reason, observations) without recording — reused by the sensitivity and onboarding suites."""
    observations, vacuous, leaks = [], [], []
    for item in questions:
        target_id = ctx.doc(item["target"])
        precondition = ctx.obs.operator_retrieve(other_tenant, item["question"])
        non_vacuous = target_id in [doc_id for doc_id, _ in precondition]
        response, record = ctx.ask(user, item["question"])
        findings = ctx.leak_findings(own_tenant, response, record)
        observations.append({"question": item["question"], "target": item["target"], "non_vacuity_precondition": non_vacuous,
                             "operator_retrieval_under_other_tenant_constraint": precondition,
                             "response": response.summary(), "audit": audit_view(record), "findings": findings})
        ctx.responses.setdefault(f"negative:{user}", []).append((response, record, own_tenant))
        if not non_vacuous:
            vacuous.append(item["target"])
        if ctx.is_leak(findings):
            leaks.append(item["question"])
    if vacuous:
        return "ERROR", f"vacuous: target document(s) {vacuous} not retrievable under {other_tenant}'s constraint", observations
    if leaks:
        foreign = sum(len(o["findings"]["foreign_retrieved"]) for o in observations)
        return "FAIL", f"{len(leaks)}/{len(questions)} questions crossed the boundary ({foreign} foreign chunks retrieved)", observations
    return "PASS", f"0 {other_tenant} documents retrieved across {len(questions)} targeted questions; preconditions met", observations


def record_negative(ctx, test_id, user, own_tenant, other_tenant, questions, suite):
    status, reason, observations = negative(ctx, user, own_tenant, other_tenant, questions)
    ctx.run.record(test_id, suite, ["SEC-001", "SEC-004", "DATA-002", "CMP-001"], ["CTL-015", "CTL-017", "CTL-018"], "L3",
                   f"BLOCKED AT RETRIEVAL: no {other_tenant} document in `retrieved`; no {other_tenant} marker in any channel",
                   status, reason, {"variant": ctx.target.variant, "questions": observations}, privileged=True)
