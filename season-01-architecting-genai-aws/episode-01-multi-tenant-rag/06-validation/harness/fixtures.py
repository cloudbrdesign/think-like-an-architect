"""Deterministic synthetic fixtures: tenants, identities and documents.

Documents are uploaded THROUGH THE API as each tenant's own user, so ownership is assigned by the ingestion service
exactly as in normal use. The loader keeps a local ownership map (fixture key → document ID → tenant) that the tests use
independently of the index's own attributes. Onboarding Tenant C uses the same functions (TST-OPS-017).
"""
import json
import os
import time

from harness.common import RESULTS, fixture_text, load_fixtures


def state_path(target):
    return os.path.join(RESULTS, "state", f"{target.stack_name}.json")


def load_state(target):
    path = state_path(target)
    return json.load(open(path)) if os.path.exists(path) else {"documents": {}}


def save_state(target, state):
    os.makedirs(os.path.dirname(state_path(target)), exist_ok=True)
    json.dump(state, open(state_path(target), "w"), indent=2, sort_keys=True)


def ownership_map(state):
    return {d["document_id"]: d["tenant"] for d in state["documents"].values() if not d.get("removed")}


def tenant_documents(state, tenant_id):
    return {doc_id for doc_id, owner in ownership_map(state).items() if owner == tenant_id}


def document_id(state, key):
    return state["documents"][key]["document_id"]


def onboard_tenant(target, identities, observer, tenant):
    """The documented onboarding procedure: one registry entry and one identity-provider membership. No code change."""
    observer.registry_put({"pk": f"TENANT#{tenant['tenant_id']}", "item_type": "TENANT", "tenant_id": tenant["tenant_id"],
                           "name": tenant["company"], "status": "ENABLED"})
    identities.ensure_group(tenant["tenant_id"])
    identities.ensure_user(tenant["user"], [tenant["tenant_id"]])


def wait_available(api, identities, user, doc_id, timeout=300):
    deadline, status = time.time() + timeout, None
    while time.time() < deadline:
        response = api.call("GET", f"/documents/{doc_id}", token=identities.access(user))
        status = (response.body or {}).get("status") if isinstance(response.body, dict) else None
        if status in ("AVAILABLE", "FAILED", "QUARANTINED", "DELETED"):
            return status
        time.sleep(5)
    return status


def wait_deleted(api, identities, user, doc_id, timeout=300):
    return wait_available(api, identities, user, doc_id, timeout)


def upload(api, identities, user, title, content):
    return api.call("POST", "/documents", token=identities.access(user), body={"title": title, "content": content})


def upload_fixture(target, api, identities, state, key, user, title, relative_file, tenant_id):
    response = upload(api, identities, user, title, fixture_text(relative_file))
    if response.status != 202:
        raise RuntimeError(f"upload of {key} failed: {response.summary()}")
    doc_id = response.body["document_id"]
    state["documents"][key] = {"document_id": doc_id, "tenant": tenant_id, "title": title, "uploaded_by": user}
    save_state(target, state)
    status = wait_available(api, identities, user, doc_id)
    if status != "AVAILABLE":
        raise RuntimeError(f"fixture {key} did not become AVAILABLE (status {status})")
    return doc_id


def load(target, identities, api, observer, document_set="ab"):
    data = load_fixtures()
    state = load_state(target)
    tenants = [t for t in data["tenants"] if not t.get("onboarding")]
    for tenant in tenants:
        onboard_tenant(target, identities, observer, tenant)
    if document_set != "ab":
        for fixture in data["identity_fixtures"]:
            identities.ensure_user(fixture["user"], fixture["groups"])
    users = {t["tenant_id"]: t["user"] for t in tenants}
    loaded = []
    for doc in data["documents"]:
        if doc.get("onboarding"):
            continue
        existing = state["documents"].get(doc["key"])
        if existing and not existing.get("removed"):
            check = api.call("GET", f"/documents/{existing['document_id']}", token=identities.access(users[doc["tenant"]]))
            if check.status == 200 and check.body.get("status") == "AVAILABLE":
                continue
        upload_fixture(target, api, identities, state, doc["key"], users[doc["tenant"]], doc["title"], doc["file"], doc["tenant"])
        loaded.append(doc["key"])
    return {"tenants": [t["tenant_id"] for t in tenants], "documents_uploaded": loaded,
            "documents_total": len(ownership_map(state))}
