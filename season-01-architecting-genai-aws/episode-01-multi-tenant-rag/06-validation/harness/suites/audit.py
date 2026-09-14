"""TST-OPS-015 — audit records are investigable and content-free; operational logs contain no content (CTL-019,
CTL-020, CTL-024)."""
import json

from harness.canary import CANARIES
from shared import audit as audit_schema

SUITE = "audit"
REQUIRED = ("event_id", "timestamp", "route", "tenant_context", "decision", "reason_code", "constraint", "retrieved",
            "verification_outcome", "outcome", "status_code", "variant")


def _questions(data):
    q = data["questions"]
    texts = [q["own_topic"], q["prompt_attack"], q["indirect_injection"], q["citation_fabrication"], q["divergence"]]
    texts += [i["question"] for key in ("cross_tenant_a_to_b", "cross_tenant_b_to_a") for i in q[key]]
    return sorted(set(texts))


def run(ctx):
    records = [r for r in (ctx.obs.audit(e, attempts=1) for e in dict.fromkeys(ctx.event_ids)) if r]
    problems = []
    missing = {r["event_id"]: [f for f in REQUIRED if r.get(f) in (None, "")] for r in records}
    missing = {k: v for k, v in missing.items() if v}
    unexpected = {r["event_id"]: sorted(set(r) - set(audit_schema.FIELDS)) for r in records if set(r) - set(audit_schema.FIELDS)}
    text = json.dumps(records)
    canaries_in_audit = {owner: text.count(prefix) for owner, prefix in CANARIES.items() if prefix in text}
    questions = _questions(ctx.data)
    questions_in_audit = [q for q in questions if q in text]
    phrases = list(CANARIES.values()) + ["Ignore all previous instructions", "Brightmoor Services charge",
                                         "maintenance manual for the north chiller", "weekend call-out rate in our cleaning"]
    log_hits = ctx.obs.log_hits(phrases, ctx.start_ms)
    log_events = ctx.obs.log_event_count(ctx.start_ms)
    model_logging = ctx.obs.model_invocation_logging_enabled()
    if not records:
        problems.append("no audit records collected")
    if missing:
        problems.append(f"{len(missing)} records missing investigation fields")
    if unexpected:
        problems.append("fields outside the audit schema")
    if canaries_in_audit or questions_in_audit:
        problems.append("content found in audit records")
    if log_hits:
        problems.append(f"content found in logs: {list(log_hits)[:3]}")
    if log_events == 0:
        problems.append("no operational log events found — log scan would be vacuous")
    if model_logging:
        problems.append("model invocation logging is enabled")
    denial = next((r for r in records if r["decision"] == "DENY"), None)
    allowed = next((r for r in records if r["decision"] == "ALLOW" and r.get("retrieved")), None)
    investigation = {name: {"who": r.get("user_id"), "which_tenant": r.get("tenant_context"), "decision": r.get("decision"),
                            "why": r.get("reason_code"), "which_control_failed": r.get("failed_control"),
                            "which_constraint": r.get("constraint"), "which_documents": r.get("retrieved")}
                     for name, r in (("allowed_example", allowed), ("denied_example", denial)) if r}
    ctx.run.record("TST-OPS-015", SUITE, ["OPS-001", "OPS-002", "CMP-001"], ["CTL-019", "CTL-020", "CTL-024"], "L3",
                   "Investigator can answer who, which tenant, decision and why, constraint, documents, failed control; "
                   "no marker, question, chunk or answer text in records or logs; model invocation logging disabled",
                   "FAIL" if problems else "PASS", "; ".join(problems) or
                   f"{len(records)} records complete and content-free; {log_events} log events scanned, 0 content hits; model logging disabled",
                   {"records_examined": len(records), "records_missing_fields": missing, "unexpected_fields": unexpected,
                    "canaries_in_audit": canaries_in_audit, "question_texts_in_audit": questions_in_audit,
                    "log_groups": ctx.obs.log_groups(), "log_events_scanned": log_events, "log_content_hits": log_hits,
                    "model_invocation_logging_enabled": model_logging, "investigation_examples": investigation},
                   privileged=True)
