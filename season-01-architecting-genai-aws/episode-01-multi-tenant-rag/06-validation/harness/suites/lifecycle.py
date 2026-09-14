"""Lifecycle: TST-DATA-014 (deletion), TST-DATA-016 (disabled tenant), TST-ASM-010 (mislabelled ingestion)."""
from harness import fixtures
from harness.context import audit_view

SUITE = "lifecycle"


def run(ctx):
    deletion(ctx)
    disabled_tenant(ctx)
    mislabelled_ingestion(ctx)


def deletion(ctx):
    doc_id, token_a = ctx.doc("A3"), ctx.ids.access("user-a")
    a1_before = ctx.obs.registry_get(f"DOC#{ctx.doc('A1')}")["status"]
    cross = ctx.api.call("DELETE", f"/documents/{ctx.doc('A1')}", token=ctx.ids.access("user-b"))
    a1_after = ctx.obs.registry_get(f"DOC#{ctx.doc('A1')}")["status"]
    delete = ctx.api.call("DELETE", f"/documents/{doc_id}", token=token_a)
    immediate, immediate_record = ctx.ask("user-a", ctx.q["deletion"])
    retrieved_now = [r["document_id"] for r in (immediate_record or {}).get("retrieved", [])]
    final_status = fixtures.wait_deleted(ctx.api, ctx.ids, "user-a", doc_id)
    later, later_record = ctx.ask("user-a", ctx.q["deletion"])
    index_status = ctx.obs.index_status(doc_id)
    problems = []
    if delete.status != 202:
        problems.append(f"delete returned {delete.status}")
    if doc_id in ((immediate_record or {}).get("cited_document_ids") or []):
        problems.append("deleting document was cited")
    if doc_id in retrieved_now and immediate_record["verification_outcome"] != "DISCARDED":
        problems.append("deleting document retrieved but not discarded")
    if final_status != "DELETED" or index_status != "NOT_FOUND":
        problems.append(f"removal not complete (status {final_status}, index {index_status})")
    if doc_id in [r["document_id"] for r in (later_record or {}).get("retrieved", [])]:
        problems.append("deleted document still retrieved")
    if cross.status != 404 or a1_before != a1_after:
        problems.append("cross-tenant delete not refused as not-found, or changed state")
    ctx.state["documents"]["A3"]["removed"] = True
    ctx.state["documents"]["A3-deleted"] = ctx.state["documents"].pop("A3")
    fixtures.save_state(ctx.target, ctx.state)
    doc = next(d for d in ctx.data["documents"] if d["key"] == "A3")
    restored = fixtures.upload_fixture(ctx.target, ctx.api, ctx.ids, ctx.state, "A3", "user-a", doc["title"], doc["file"], "tenant-a")
    ctx.run.record("TST-DATA-014", SUITE, ["FUN-003"], ["CTL-014", "CTL-017"], "L3",
                   "Immediately: not cited (discarded if retrieved). After removal: absent from index, status DELETED. "
                   "Cross-tenant delete: not found, nothing changed", "FAIL" if problems else "PASS",
                   "; ".join(problems) or f"deleted document never cited; removed from index; cross-tenant delete not found (fixture restored)",
                   {"delete": delete.summary(), "immediate": audit_view(immediate_record), "final_status": final_status,
                    "index_status": index_status, "later": audit_view(later_record), "cross_tenant_delete": cross.summary(),
                    "a1_status_before_after": [a1_before, a1_after], "restored_fixture_document_id": restored})


def disabled_tenant(ctx):
    observations, problems = {}, []
    before = len(ctx.obs.document_records())
    try:
        ctx.obs.set_tenant_status("tenant-b", "DISABLED")
        response, record = ctx.ask("user-b", ctx.q["own_topic"])
        upload = ctx.api.call("POST", "/documents", token=ctx.ids.access("user-b"), body={"title": "t", "content": "c"})
        after = len(ctx.obs.document_records())
        cross, cross_record = ctx.ask("user-a", ctx.q["cross_tenant_a_to_b"][0]["question"])
        findings = ctx.leak_findings("tenant-a", cross, cross_record)
        observations = {"query": {"response": response.summary(), "audit": audit_view(record)},
                        "upload": upload.summary(), "document_records_before_after": [before, after],
                        "tenant_a_cross_question": {"audit": audit_view(cross_record), "findings": findings}}
        if response.code() != "TENANT_DISABLED" or (record or {}).get("retrieved"):
            problems.append("disabled tenant query not refused before retrieval")
        if upload.code() != "TENANT_DISABLED" or after != before:
            problems.append("disabled tenant upload not refused")
        if ctx.is_leak(findings):
            problems.append("tenant-b document retrieved by tenant-a")
    finally:
        ctx.obs.set_tenant_status("tenant-b", "ENABLED")
    ctx.run.record("TST-DATA-016", SUITE, ["BUS-001"], ["CTL-005"], "L3",
                   "user-b query and upload denied TENANT_DISABLED; no retrieval; Tenant B documents never retrieved by anyone",
                   "FAIL" if problems else "PASS", "; ".join(problems) or "query and upload refused while disabled; tenant re-enabled",
                   observations, privileged=True)


def mislabelled_ingestion(ctx):
    passed, tail = ctx.component_tests(["test_ingestion_attribution.AttributionGateTests",
                                        "test_ingestion_attribution.IngestionHandlerTests.test_inconsistent_attribution_is_quarantined_and_never_indexed"])
    edge = ctx.data["edge_cases"]["E3"]
    doc_id = fixtures.upload_fixture(ctx.target, ctx.api, ctx.ids, ctx.state, "E3", "user-a", edge["title"], edge["file"], "tenant-a")
    record = ctx.obs.registry_get(f"DOC#{doc_id}")
    question = "What weekend call-out rates are seen in the market according to the forwarded rate sheet?"
    a_response, a_record = ctx.ask("user-a", question)
    b_response, b_record = ctx.ask("user-b", question)
    a_retrieved = [r["document_id"] for r in (a_record or {}).get("retrieved", [])]
    b_retrieved = [r["document_id"] for r in (b_record or {}).get("retrieved", [])]
    delete = ctx.api.call("DELETE", f"/documents/{doc_id}", token=ctx.ids.access("user-a"))
    final = fixtures.wait_deleted(ctx.api, ctx.ids, "user-a", doc_id)
    ctx.state["documents"]["E3"]["removed"] = True
    fixtures.save_state(ctx.target, ctx.state)
    problems = []
    if not passed:
        problems.append("(a) component quarantine tests failed")
    if record["owner"] != "tenant-a" or doc_id not in a_retrieved or doc_id in b_retrieved:
        problems.append("(b) document not confined to the uploader's tenant")
    if final != "DELETED":
        problems.append("(b) fixture not removed")
    ctx.run.record("TST-ASM-010", SUITE, ["SEC-006", "DATA-003"], ["CTL-012", "CTL-011", "CTL-019", "CTL-013"], "L4",
                   "(a) inconsistent attribution quarantined, never indexed. (b) a Tenant A upload carrying a Tenant B "
                   "marker stays Tenant A's: retrievable by user-a only, uploader and retrievals recorded (RR-03)",
                   "FAIL" if problems else "PASS",
                   "; ".join(problems) or "(a) quarantine verified at component level; (b) exposed as residual risk RR-03, confined to tenant-a, removed",
                   {"a_component_tests": {"passed": passed, "output": tail},
                    "b_record": {k: record.get(k) for k in ("document_id", "owner", "uploader", "created_at")},
                    "b_user_a": audit_view(a_record), "b_user_b": audit_view(b_record),
                    "b_removal": {"delete": delete.summary(), "final_status": final}})
