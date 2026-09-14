"""Ingestion attribution: TST-SEC-019 (upload tries to choose the tenant) and TST-SEC-020 (ownership change)."""
import os
import sys

from harness import fixtures
from harness.common import IMPLEMENTATION, fixture_text

SUITE = "ingestion"


def run(ctx):
    choose_tenant(ctx)
    change_ownership(ctx)


def choose_tenant(ctx):
    before = len(ctx.obs.document_records())
    token = ctx.ids.access("user-a")
    refused = {}
    for field, value in (("tenant_id", "tenant-b"), ("owner", "tenant-b"), ("owning_tenant", "tenant-b"),
                         ("document_id", "0b6f1f5e-8f7a-4c1e-9d2a-3c4b5a6d7e8f")):
        reply = ctx.api.call("POST", "/documents", token=token, body={"title": "Rates", "content": "text", field: value})
        refused[field] = reply.summary()
    after = len(ctx.obs.document_records())
    edge = ctx.data["edge_cases"]["E2"]
    doc_id = fixtures.upload_fixture(ctx.target, ctx.api, ctx.ids, ctx.state, "E2", "user-a", edge["title"], edge["file"], "tenant-a")
    record = ctx.obs.registry_get(f"DOC#{doc_id}")
    user_a_sub = ctx.ids.claims(token)["sub"]
    other_open = ctx.api.call("GET", f"/documents/{doc_id}", token=ctx.ids.access("user-b"))
    problems = [f"{f} not refused" for f, r in refused.items() if r["code"] != "REQUEST_FIELD_REJECTED"]
    if after != before:
        problems.append("a refused upload created an ownership record")
    if (record or {}).get("owner") != "tenant-a" or record.get("uploader") != user_a_sub or not record.get("created_at"):
        problems.append("embedded-owner document not attributed to tenant-a with uploader and time")
    if other_open.status != 404:
        problems.append("tenant-b can open the tenant-a document")
    ctx.run.record("TST-SEC-019", SUITE, ["SEC-006", "DATA-001"], ["CTL-011"], "L3",
                   "Owner, tenant and ID fields refused; content claiming another owner attributed to Tenant A with owner, "
                   "uploader, time and status", "FAIL" if problems else "PASS",
                   "; ".join(problems) or "4 field attempts refused, nothing stored; embedded claim ignored; owner tenant-a",
                   {"refused_uploads": refused, "document_records_before_after": [before, after],
                    "embedded_owner_document": {k: record.get(k) for k in ("document_id", "owner", "uploader", "created_at", "status", "title")},
                    "tenant_b_open": other_open.summary()})


def change_ownership(ctx):
    sys.path.insert(0, os.path.join(IMPLEMENTATION, "scripts", "operator"))
    import correct_attribution
    doc_id = ctx.doc("E2")
    token = ctx.ids.access("user-a")
    attempts = {
        "PUT /documents/{id}": ctx.api.call("PUT", f"/documents/{doc_id}", token=token, body={"owner": "tenant-b"}).summary(),
        "PATCH /documents/{id}": ctx.api.call("PATCH", f"/documents/{doc_id}", token=token, body={"owner": "tenant-b"}).summary(),
        "re-upload claiming the same identifier": ctx.api.call("POST", "/documents", token=token, body={
            "title": "t", "content": "c", "document_id": doc_id}).summary(),
    }
    problems = []
    if attempts["PUT /documents/{id}"]["status"] not in (404, 405) or attempts["PATCH /documents/{id}"]["status"] not in (404, 405):
        problems.append("an update route exists")
    if attempts["re-upload claiming the same identifier"]["code"] != "REQUEST_FIELD_REJECTED":
        problems.append("identifier claim not refused")
    unchanged = ctx.obs.registry_get(f"DOC#{doc_id}")["owner"] == "tenant-a"
    correction = correct_attribution.correct(ctx.target.session, ctx.target.outputs, doc_id, "tenant-b",
                                             "TST-SEC-020 fixture: window schedule filed under Northwall in error",
                                             ctx.target.caller)
    step_records = [ctx.obs.audit(step["event_id"]) for step in correction["steps"]]
    original = ctx.obs.registry_get(f"DOC#{doc_id}")
    ctx.state["documents"]["E2"]["removed"] = True
    fixtures.save_state(ctx.target, ctx.state)
    edge = ctx.data["edge_cases"]["E2"]
    new_id = fixtures.upload_fixture(ctx.target, ctx.api, ctx.ids, ctx.state, "E2-corrected", "user-b", edge["title"], edge["file"], "tenant-b")
    new_record = ctx.obs.registry_get(f"DOC#{new_id}")
    if not unchanged:
        problems.append("owner changed before correction")
    if len([r for r in step_records if r and r.get("action") == "OPERATOR_CORRECTION"]) != 4:
        problems.append("correction not recorded step by step")
    if original["owner"] != "tenant-a" or original["status"] != "REMOVED_FOR_CORRECTION":
        problems.append("original record was edited in place instead of removed")
    if new_record["owner"] != "tenant-b":
        problems.append("re-upload not owned by tenant-b")
    ctx.run.record("TST-SEC-020", SUITE, ["SEC-007"], ["CTL-013", "CTL-010"], "L3",
                   "User attempts refused (no route or field refused); operator correction recorded step by step; "
                   "ownership never edited in place", "FAIL" if problems else "PASS",
                   "; ".join(problems) or "no user route changes ownership; 4 recorded correction steps; new tenant-b document via normal upload",
                   {"user_attempts": attempts,
                    "correction_steps": [{k: (r or {}).get(k) for k in ("correction_step", "outcome", "document_id", "operator_reason")} for r in step_records],
                    "original_record_after": {k: original.get(k) for k in ("owner", "status")},
                    "reuploaded_document": {k: new_record.get(k) for k in ("document_id", "owner", "status")}},
                   privileged=True)
