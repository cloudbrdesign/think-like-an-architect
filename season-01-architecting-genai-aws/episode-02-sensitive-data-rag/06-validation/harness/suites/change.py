"""Change tests TST-CHG-001 (revocation with an unchanged token) and TST-CHG-002 (upward reclassification without re-index)."""
import json

from harness import canaries, fixtures
from harness.suites import test


@test("TST-CHG-001", "change", ["SEC-010", "SEC-003", "BUS-002"], ["CTL-003"], "L4",
      "After P-02's BID-ORION grant is revoked in the grants store, the same still-valid token retrieves no BID-ORION content")
def chg_001(ctx):
    persona = ctx.personas["P-02"]
    username = persona["username"]
    subject = ctx.ids.subject(username)
    ddb, table = ctx.target.client("dynamodb"), ctx.target.outputs["AuthorizationTable"]
    token = ctx.ids.token(username, fresh=True)
    claims = ctx.ids.claims(token)
    version = ctx.obs.grants_item(subject, "GRANTS")["grants_version"]
    before = ctx.ask("P-02", "orion_pricing", token=token)
    try:
        fixtures.put_grants(ddb, table, subject, persona, domains=[], grants_version=version + 1)
        ctx.ids.set_groups(username, [])                      # the directory changes too; the issued token does not
        after = ctx.ask("P-02", "orion_pricing", token=token)
    finally:
        fixtures.put_grants(ddb, table, subject, persona, grants_version=version + 2)
        ctx.ids.set_groups(username, ctx.ids.group_names(persona))
        ctx.ids.token(username, fresh=True)
    bid = {"D-03-S4", "D-14-S1"}
    decision = (after.audit or {}).get("decision") or {}
    same_token = before.token_sha256 == after.token_sha256
    passed = (same_token and "D-03-S4" in before.retrieved_keys and not bid & set(after.retrieved_keys)
              and decision.get("grants_version") == version + 1 and decision.get("domains") == [] and not ctx.leaks(after))
    return passed, f"same token: {same_token} (groups claim {claims.get('cognito:groups')}); before retrieved D-03 §4: " \
        f"{'D-03-S4' in before.retrieved_keys}; after revocation retrieved BID-ORION: {sorted(bid & set(after.retrieved_keys))}; " \
        f"decision domains {decision.get('domains')} grants_version {decision.get('grants_version')} (revoked version {version + 1})", \
        {"token_groups_claim": claims.get("cognito:groups"), "before": before.view(), "after": after.view(),
         "grants_versions": {"before": version, "revoked": version + 1, "restored": version + 2}}


@test("TST-CHG-002", "change", ["SEC-011"], ["CTL-014"], "L4",
      "D-13 reclassified upward without re-index: withheld before generation for P-01 and P-07; answers resume after re-index")
def chg_002(ctx):
    ddb, table = ctx.target.client("dynamodb"), ctx.target.outputs["ClassificationTable"]
    item = ctx.obs.classification_item("D-13")
    original = json.loads(item["record"])
    version = original["version"]
    before = ctx.ask("P-01", "resilience")
    changed = dict(original, document_label="CONFIDENTIAL", document_scope="OPS-LEADERSHIP", version=version + 1)
    withheld = []
    try:
        fixtures.put_classification(ddb, table, changed)
        withheld = [ctx.ask("P-01", "resilience"), ctx.ask("P-07", "resilience")]
    finally:
        fixtures.put_classification(ddb, table, dict(original, version=version + 2))
        reingest = fixtures.invoke_ingestion(ctx.target, ["D-13"])
    after = ctx.ask("P-01", "resilience")
    contained = all(o.outcome == "WITHHELD_VERIFICATION_MISMATCH" and not o.generation_invoked and o.uniform
                    and any(m["reason"] in ("LABEL_MISMATCH", "SCOPE_MISMATCH", "VERSION_MISMATCH")
                            for m in (o.audit or {}).get("verification", {}).get("mismatches", [])) for o in withheld)
    after_ok = "D-13-S1" in after.retrieved_keys and after.outcome != "WITHHELD_VERIFICATION_MISMATCH"
    passed = "D-13-S1" in before.retrieved_keys and contained and after_ok
    return passed, f"before: D-13 retrieved {('D-13-S1' in before.retrieved_keys)}; after reclassification: " \
        f"{[(o.persona, o.outcome) for o in withheld]}; after restore + re-index: {after.outcome}", \
        {"before": before.view(), "reclassified": {"from": [original["document_label"], original.get("document_scope")],
                                                   "to": ["CONFIDENTIAL", "OPS-LEADERSHIP"], "version": version + 1},
         "withheld": [o.view() for o in withheld], "restore_ingestion": reingest["index_status"], "after": after.view(),
         "episode_03_boundary": "answers resume only after re-indexing; propagating classification changes to the index is Episode 03"}


def _unused():  # keeps the canaries import meaningful for readers of this module
    return canaries
