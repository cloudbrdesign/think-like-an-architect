"""TST-OPS-017 — onboard Tenant C with one registry entry and one membership: no code, template or deployment change."""
import hashlib
import os

from harness import fixtures
from harness.common import IMPLEMENTATION
from harness.suites.isolation import negative

SUITE = "onboarding"


def _tree_hash():
    digest = hashlib.sha256()
    for base in ("app", "infrastructure"):
        for directory, dirs, files in sorted(os.walk(os.path.join(IMPLEMENTATION, base))):
            dirs[:] = sorted(d for d in dirs if d != "__pycache__")
            for name in sorted(files):
                if not name.endswith(".pyc"):
                    path = os.path.join(directory, name)
                    digest.update(os.path.relpath(path, IMPLEMENTATION).encode())
                    digest.update(open(path, "rb").read())
    return digest.hexdigest()


def _deployment_fingerprint(ctx):
    t = ctx.target
    stack = t.client("cloudformation").describe_stacks(StackName=t.stack_name)["Stacks"][0]
    lam = t.client("lambda")
    return {"source_tree_sha256": _tree_hash(),
            "stack_last_updated": str(stack.get("LastUpdatedTime") or stack["CreationTime"]),
            "query_code": lam.get_function_configuration(FunctionName=t.outputs["QueryFunctionName"])["CodeSha256"],
            "ingestion_code": lam.get_function_configuration(FunctionName=t.outputs["IngestionFunctionName"])["CodeSha256"]}


def run(ctx):
    before = _deployment_fingerprint(ctx)
    tenant_c = next(t for t in ctx.data["tenants"] if t["tenant_id"] == "tenant-c")
    fixtures.onboard_tenant(ctx.target, ctx.ids, ctx.obs, tenant_c)
    for doc in ctx.data["documents"]:
        if doc["tenant"] == "tenant-c" and not ctx.state["documents"].get(doc["key"]):
            fixtures.upload_fixture(ctx.target, ctx.api, ctx.ids, ctx.state, doc["key"], "user-c", doc["title"], doc["file"], "tenant-c")
    after = _deployment_fingerprint(ctx)
    response, record = ctx.ask("user-c", ctx.q["own_topic"])
    own_ok = response.status == 200 and record and record["retrieved"] and all(
        r["owner_attribute"] == "tenant-c" and r["document_id"] in ctx.own("tenant-c") for r in record["retrieved"])
    results = {
        "C→A": negative(ctx, "user-c", "tenant-c", "tenant-a", ctx.q["onboarding_c_to_a"]),
        "C→B": negative(ctx, "user-c", "tenant-c", "tenant-b", ctx.q["onboarding_c_to_b"]),
        "A→C": negative(ctx, "user-a", "tenant-a", "tenant-c", ctx.q["onboarding_a_to_c"]),
    }
    problems = []
    if before != after:
        problems.append("code, template or deployment changed during onboarding")
    if not own_ok:
        problems.append("tenant-c positive retrieval failed")
    problems += [f"{k}: {status} {reason}" for k, (status, reason, _) in results.items() if status != "PASS"]
    status = "PASS" if not problems else ("ERROR" if all(s in ("PASS", "ERROR") for s, _, _ in results.values()) and before == after and own_ok else "FAIL")
    ctx.run.record("TST-OPS-017", SUITE, ["BUS-002", "NFR-002"], ["CTL-005", "CTL-006"], "L3",
                   "No code, template or deployment change; isolation holds across A, B and C", status,
                   "; ".join(problems) or "tenant-c onboarded by registry entry + membership only; C↔A, C↔B, A→C isolated",
                   {"fingerprint_before": before, "fingerprint_after": after,
                    "tenant_c_own_question": {"response": response.summary(), "retrieved": (record or {}).get("retrieved")},
                    "isolation": {k: {"status": s, "reason": r, "questions": o} for k, (s, r, o) in results.items()}},
                   privileged=True)
