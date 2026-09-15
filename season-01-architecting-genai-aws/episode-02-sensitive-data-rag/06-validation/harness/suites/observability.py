"""Observability and scale tests: TST-OBS-001, TST-OBS-002, TST-SCALE-001."""
import json
import re

from harness import canaries
from harness.suites import test
from core import constraints, tier_selection, verification
from core.eligibility import allow, refuse, DENIED

CANARY = re.compile(r"CANARY-[A-Z0-9-]+")


@test("TST-OBS-001", "observability", ["SEC-012", "DATA-006"], ["CTL-018", "CTL-019"], "L3",
      "No canary and no question text in any audit record or operational log; decisions present; model logging disabled")
def obs_001(ctx):
    raw = json.dumps(ctx.obs.raw_audit_table())
    canary_hits = sorted(set(CANARY.findall(raw)))
    question_hits = sorted(q for q in ctx.sent_questions if q in raw)
    items = [i for i in ctx.obs.audit_items() if i.get("record_type") == "QUERY"]
    incomplete = [i["request_id"] for i in items if not i.get("outcome") or "question" in i]
    phrases = ["CANARY-"] + sorted(ctx.sent_questions)
    log_hits, log_events = ctx.obs.log_hits(phrases, ctx.started_ms)
    logging_enabled = ctx.obs.model_invocation_logging_enabled()
    passed = not canary_hits and not question_hits and not incomplete and not log_hits and not logging_enabled and items
    scan = {"audit_items": len(items), "canary_hits_in_audit": canary_hits, "question_text_hits_in_audit": question_hits,
            "items_without_outcome": incomplete, "log_events_scanned": log_events, "log_hits": log_hits,
            "questions_searched": len(ctx.sent_questions), "model_invocation_logging_enabled": logging_enabled}
    ctx.run.attach("canary-scan.json", scan)
    return bool(passed), f"{len(items)} audit items, {log_events} log events scanned; canary hits {canary_hits}; question " \
        f"hits {len(question_hits)}; log hits {log_hits}; model logging enabled {logging_enabled}", scan


def _reconstruct(ctx, request_id):
    audit = ctx.obs.audit(request_id)
    decision_record = audit.get("decision") or {}
    subject = audit["requester_sub"]
    hr = ctx.obs.grants_item(subject, f"HR#v{decision_record.get('hr_version')}")
    grants = ctx.obs.grants_item(subject, f"GRANTS#v{decision_record.get('grants_version')}")
    if hr and hr["employment_status"] == "ACTIVE" and grants:
        decision = allow(subject, grants["domains"], grants["cases"], hr["hr_version"], grants["grants_version"])
    else:
        decision = refuse(subject, DENIED, "REFUSED_NO_ACTIVE_EMPLOYMENT")
    hashes = []
    if decision.allowed:
        hashes = [q.filter_sha256 for q in constraints.build_tier_queries(decision, tier_selection.select_tiers(decision))]
    versions = (audit.get("verification") or {}).get("record_versions", {})
    records = {}
    for document_id, version in versions.items():
        item = ctx.obs.classification_item(f"HISTORY#{document_id}#v{version}")
        records[document_id] = json.loads(item["record"]) if item else None
    chunks = [verification.RetrievedChunk(e["chunk_id"], e["tier"], e["document_id"], e["section_id"], e["label"],
                                          e["scope"], e["record_version"], e["score"], "") for e in audit.get("retrieval", [])]
    result = verification.verify(decision, chunks, records) if chunks else None
    expected_outcome = (decision.outcome if not decision.allowed else "NO_ELIGIBLE_CONTENT" if not chunks
                        else "WITHHELD_VERIFICATION_MISMATCH" if result.status != "PASS" else "ANSWERED_OR_NOT_RELEVANT")
    observed = audit["outcome"] if expected_outcome != "ANSWERED_OR_NOT_RELEVANT" or audit["outcome"] not in (
        "ANSWERED", "NO_RELEVANT_CONTENT") else "ANSWERED_OR_NOT_RELEVANT"
    checks = {"decision": [list(decision.domains), list(decision.cases)] == [decision_record.get("domains"), decision_record.get("cases")],
              "constraint_hashes": hashes == [c["sha256"] for c in audit.get("constraints", [])],
              "verification": (result is None and audit["verification"]["status"] == "NOT_RUN") or (
                  result is not None and result.status == audit["verification"]["status"]
                  and [r for _, r in result.mismatches] == [m["reason"] for m in audit["verification"]["mismatches"]]),
              "outcome": expected_outcome == observed}
    return {"request_id": request_id, "checks": checks, "reconstructed": {
        "decision": {"status": decision.status, "domains": list(decision.domains), "cases": list(decision.cases),
                     "hr_version": decision.hr_version, "grants_version": decision.grants_version},
        "constraint_hashes": hashes, "verification": result and {"status": result.status, "mismatches": list(result.mismatches)},
        "expected_outcome": expected_outcome}, "audit_outcome": audit["outcome"]}


@test("TST-OBS-002", "observability", ["OPS-001", "OPS-002"], ["CTL-020"], "L3",
      "Three decisions reconstructed from audit records and stored versions match; reports list the quarantined fixtures "
      "and the TST-SEC-007 mismatch")
def obs_002(ctx):
    wanted = {k: ctx.marks.get(k) for k in ("TST-ELG-003", "TST-SEC-007", "TST-DATA-001")}
    if not all(wanted.values()):
        return False, f"source requests missing: {wanted}", {}
    reconstructions = [_reconstruct(ctx, rid) for rid in wanted.values()]
    reports = ctx.obs.ingestion_reports()
    quarantined = sorted({q["document_id"] for r in reports for q in r.get("quarantine", [])})
    mismatch_report = [{"request_id": i["request_id"], "mismatches": i["verification"]["mismatches"]}
                       for i in ctx.obs.audit_items() if i.get("record_type") == "QUERY"
                       and (i.get("verification") or {}).get("status") == "MISMATCH"]
    ctx.run.attach("reconstruction.json", reconstructions)
    ctx.run.attach("quarantine-report.json", [{"request_id": r["request_id"], "quarantine": r["quarantine"],
                                               "special_category_excluded": r["special_category_excluded"]} for r in reports])
    ctx.run.attach("mismatch-report.json", mismatch_report)
    reconstructed = all(all(r["checks"].values()) for r in reconstructions)
    passed = (reconstructed and {"D-09", "D-10", "D-11", "D-15"} <= set(quarantined)
              and any(m["request_id"] == wanted["TST-SEC-007"] for m in mismatch_report))
    return passed, f"reconstruction checks {[r['checks'] for r in reconstructions]}; quarantine report {quarantined}; " \
        f"mismatch report includes TST-SEC-007: {any(m['request_id'] == wanted['TST-SEC-007'] for m in mismatch_report)}", \
        {"sources": wanted, "reconstructions": reconstructions, "quarantined_documents": quarantined,
         "mismatch_requests": len(mismatch_report)}


def _largest_accepted_domains():
    """The largest domain list the application's own builder accepts (FIN-REPORTING last)."""
    low, high = 1, 2000
    while high - low > 1:
        middle = (low + high) // 2
        domains = [f"SYN-PROBE-{i:04d}" for i in range(middle)] + ["FIN-REPORTING"]
        try:
            constraints.build_tier_queries(allow("probe", domains, [], 1, 1), ("shared",))
            low = middle
        except Exception:  # noqa: BLE001 — refusal above the budget
            high = middle
    return [f"SYN-PROBE-{i:04d}" for i in range(low)] + ["FIN-REPORTING"]


@test("TST-SCALE-001", "scale", ["NFR-001", "NFR-002"], ["CTL-003", "CTL-013"], "L4",
      "P-10 (40 grants) retrieves D-08 and nothing ineligible; the over-limit persona is refused before any search, never "
      "truncated; the largest constraint the application accepts is accepted by the service with its last grant honoured")
def scale_001(ctx):
    from harness import platform
    p10 = ctx.ask("P-10", "finance")
    p11 = ctx.ask("P-11", "finance")
    p10_ok = "D-08-S1" in p10.retrieved_keys and not ctx.leaks(p10) and p10.outcome == "ANSWERED"
    p11_ok = (p11.outcome == "REFUSED_CONSTRAINT_INCOMPLETE" and not p11.tiers_called and not p11.retrieved_keys
              and p11.uniform)
    largest = _largest_accepted_domains()
    budget_edge = constraints.build_tier_queries(allow("probe", largest, [], 1, 1), ("shared",))[0]
    at_budget = platform.probe(ctx.target, "SYN-PROBE-", len(largest) - 1)
    above_limit = platform.probe(ctx.target, "SYN-PROBE-", 700)
    budget_ok = at_budget["accepted"] and at_budget["last_grant_honoured"] and not above_limit["accepted"]
    constraint_bytes = [c["bytes"] for c in (p10.audit or {}).get("constraints", [])]
    return p10_ok and p11_ok and budget_ok, f"P-10 retrieved D-08: {'D-08-S1' in p10.retrieved_keys}, leaks {ctx.leaks(p10)}, " \
        f"constraint {constraint_bytes} bytes, decision {((p10.audit or {}).get('latency_ms') or {}).get('decision')} ms; " \
        f"P-11 outcome {p11.outcome}, tiers {p11.tiers_called}; largest application-accepted constraint " \
        f"({len(largest)} grants, {budget_edge.filter_bytes} bytes) accepted by the service: {at_budget['accepted']}, last grant " \
        f"honoured: {at_budget.get('last_grant_honoured')}; above the observed limit rejected: {not above_limit['accepted']} " \
        f"({above_limit.get('layer')})", \
        {"p10": p10.view(), "p11": p11.view(), "application_budget_bytes": constraints.CONSTRAINT_BUDGET_BYTES,
         "observed_limits_bytes": {"retrieve_api": constraints.RETRIEVE_API_OBSERVED_LIMIT_BYTES,
                                   "vector_store": constraints.VECTOR_STORE_OBSERVED_LIMIT_BYTES},
         "largest_application_accepted_constraint": {"grants": len(largest), "bytes": budget_edge.filter_bytes},
         "platform_probe_at_budget_privileged": at_budget, "platform_probe_above_limit_privileged": above_limit,
         "note": "Observed platform behaviour under the tested conditions, not an architectural constant"}


def _unused():
    return canaries
