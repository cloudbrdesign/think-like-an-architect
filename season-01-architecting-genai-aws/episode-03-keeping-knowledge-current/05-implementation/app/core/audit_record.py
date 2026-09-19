"""The content-free audit record (CTL-018, CTL-036; Episode 02 ADR-006, Episode 03 ADR-007). Schema tla-e03-audit/1.

It reconstructs the decision: who asked, which authoritative grant versions were used, which tiers were searched with
which constraint (hash and size), which chunks crossed the retrieval boundary, what verification decided — and, new in
Episode 03, what the system could say about currency and convergence at that moment:

    convergence   the state of each candidate document (KNOWN_CURRENT | KNOWN_PENDING | KNOWN_… | UNKNOWN)
    freshness     the claim the evidence supported: proven watermark floor, pending count, oldest pending age,
                  reconciliation age, and whether the request was answered in conservative mode

It NEVER contains the question (neither text nor hash), document or chunk text, the answer, special-category data,
tokens, credentials or secrets. validate() enforces that with allow-lists at every level.
"""
from datetime import datetime, timezone

SCHEMA = "tla-e03-audit/1"
TOP_LEVEL = frozenset({
    "request_id", "schema", "record_type", "timestamp", "deployment", "variant", "requester_sub", "employee_id",
    "decision", "tiers_called", "constraints", "retrieval", "verification", "convergence", "freshness", "relevance",
    "generation", "outcome", "failing_control", "detail", "latency_ms", "incomplete"})
DECISION = frozenset({"status", "hr_version", "grants_version", "domains", "cases"})
CONSTRAINT = frozenset({"tier", "sha256", "bytes"})
RETRIEVAL = frozenset({"chunk_id", "tier", "document_id", "section_id", "label", "scope", "record_version", "score"})
VERIFICATION = frozenset({"status", "mismatches", "record_versions"})
MISMATCH = frozenset({"chunk_id", "reason"})
CONVERGENCE = frozenset({"available", "document_states", "pending"})
PENDING = frozenset({"document_id", "change_class", "effective_version", "noticed_at", "detail"})
FRESHNESS = frozenset({"claim", "global_floor", "limiting_change_class", "pending_total", "oldest_pending_age_seconds",
                       "last_reconciliation_completed_at", "reconciliation_age_seconds", "reconciliation_overdue",
                       "inside_windows", "conservative_mode"})
RELEVANCE = frozenset({"min_score", "kept", "omitted"})
GENERATION = frozenset({"invoked", "model_id", "input_tokens", "output_tokens"})
LATENCY = frozenset({"decision", "retrieval", "verification", "convergence", "generation", "total"})


class AuditSchemaError(ValueError):
    pass


def new(request_id, deployment, variant):
    return {"request_id": request_id, "schema": SCHEMA, "record_type": "QUERY",
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="milliseconds"), "deployment": deployment,
            "variant": variant, "requester_sub": None, "employee_id": None, "decision": None, "tiers_called": [],
            "constraints": [], "retrieval": [], "verification": {"status": "NOT_RUN", "mismatches": []},
            "convergence": {"available": None, "document_states": {}, "pending": []}, "freshness": None,
            "relevance": None, "generation": {"invoked": False}, "outcome": None, "failing_control": None,
            "detail": None, "latency_ms": {}}


def _only(value, allowed, where):
    if not isinstance(value, dict):
        raise AuditSchemaError(f"{where} must be an object")
    extra = set(value) - allowed
    if extra:
        raise AuditSchemaError(f"{where}: fields not in the audit schema: {sorted(extra)}")


def _scalar(value, where):
    if isinstance(value, (dict, list)):
        raise AuditSchemaError(f"{where} must be a scalar")


def validate(record):
    _only(record, TOP_LEVEL, "record")
    if record.get("decision") is not None:
        _only(record["decision"], DECISION, "decision")
    for item in record.get("constraints", []):
        _only(item, CONSTRAINT, "constraints[]")
    for item in record.get("retrieval", []):
        _only(item, RETRIEVAL, "retrieval[]")
        for key, value in item.items():
            _scalar(value, f"retrieval[].{key}")
    _only(record.get("verification", {}), VERIFICATION, "verification")
    for item in record.get("verification", {}).get("mismatches", []):
        _only(item, MISMATCH, "verification.mismatches[]")
    versions = record.get("verification", {}).get("record_versions", {})
    if not isinstance(versions, dict) or not all(isinstance(k, str) and isinstance(v, int) for k, v in versions.items()):
        raise AuditSchemaError("verification.record_versions maps document identifiers to versions only")
    convergence = record.get("convergence") or {}
    _only(convergence, CONVERGENCE, "convergence")
    document_states = convergence.get("document_states", {})
    if not isinstance(document_states, dict) or not all(isinstance(k, str) and isinstance(v, str)
                                                        for k, v in document_states.items()):
        raise AuditSchemaError("convergence.document_states maps document identifiers to state names only")
    for item in convergence.get("pending", []):
        _only(item, PENDING, "convergence.pending[]")
        for key, value in item.items():
            _scalar(value, f"convergence.pending[].{key}")
    if record.get("freshness") is not None:
        _only(record["freshness"], FRESHNESS, "freshness")
        for key, value in record["freshness"].items():
            _scalar(value, f"freshness.{key}")
    if record.get("relevance") is not None:
        _only(record["relevance"], RELEVANCE, "relevance")
        for key in ("kept", "omitted"):
            if not all(isinstance(v, str) for v in record["relevance"].get(key, [])):
                raise AuditSchemaError("relevance lists hold chunk identifiers only")
    _only(record.get("generation", {}), GENERATION, "generation")
    _only(record.get("latency_ms", {}), LATENCY, "latency_ms")
    for key in ("request_id", "requester_sub", "employee_id", "outcome", "failing_control", "detail", "deployment",
                "variant"):
        _scalar(record.get(key), key)
    if isinstance(record.get("detail"), str) and len(record["detail"]) > 120:
        raise AuditSchemaError("detail is a short code, never content")
    return record


def retrieval_entry(chunk):
    return {"chunk_id": chunk.chunk_id, "tier": chunk.tier, "document_id": chunk.document_id,
            "section_id": chunk.section_id, "label": chunk.label, "scope": chunk.scope,
            "record_version": chunk.record_version, "score": round(float(chunk.score), 6)}


def freshness_entry(claim, conservative):
    """The freshness fields kept in the audit record: the claim and the facts behind it, never queue depth."""
    return {key: claim.get(key) for key in FRESHNESS if key in claim} | {"conservative_mode": conservative}
