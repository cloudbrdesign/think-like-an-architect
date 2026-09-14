"""Content-minimising security audit (CTL-019, CTL-020; ADR-006). Schema tla-audit/1.

One record per request, keyed by event_id and returned to the caller as the x-tla-event-id header.
The record answers: who, which tenant, allowed or denied and why, which control, which constraint, which documents
crossed the retrieval boundary (before verification), what verification decided, and what was cited.

It never contains the token, the question text, retrieved chunk text, the generated answer or document content.
The allow-list below enforces that: a field not listed cannot be written.
"""
import json
import time
from datetime import datetime, timezone

from shared.dynamo import to_attr, to_item

SCHEMA = "tla-audit/1"
FIELDS = ("event_id", "schema", "timestamp", "variant", "route", "action", "request_id", "user_id", "token_issuer",
          "client_id", "tenant_context", "decision", "reason_code", "failed_control", "constraint", "constraint_sha256",
          "knowledge_base_id", "retrieved", "verification_outcome", "discarded_count", "cited_document_ids",
          "document_id", "outcome", "status_code", "question_length", "latency_ms",
          "correction_step", "operator_reason")  # the last two: privileged operator correction workflow only (CTL-010)
LOG_FIELDS = ("event_id", "route", "reason_code", "status_code", "latency_ms", "error_class", "message")


class AuditWriteFailed(Exception):
    pass


def new_record(event_id, route, action, event, variant):
    return {"event_id": event_id, "schema": SCHEMA, "variant": variant, "route": route, "action": action,
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "request_id": ((event or {}).get("requestContext") or {}).get("requestId"),
            "user_id": None, "token_issuer": None, "client_id": None, "tenant_context": "NONE", "decision": "DENY",
            "reason_code": None, "failed_control": None, "constraint": "NONE", "constraint_sha256": None,
            "knowledge_base_id": None, "retrieved": [], "verification_outcome": "NOT_APPLICABLE", "discarded_count": 0,
            "cited_document_ids": [], "document_id": None, "outcome": "PENDING", "status_code": None,
            "question_length": None, "latency_ms": None}


def elapsed_ms(started):
    return int((time.monotonic() - started) * 1000)


class AuditLog:
    def __init__(self, client, table_name):
        self._client = client
        self._table = table_name

    def write_decision(self, record):
        unexpected = set(record) - set(FIELDS)
        if unexpected:
            raise AuditWriteFailed(f"field(s) not in the audit schema: {sorted(unexpected)}")
        try:
            self._client.put_item(TableName=self._table, Item=to_item(record),
                                  ConditionExpression="attribute_not_exists(event_id)")
        except Exception as error:  # noqa: BLE001
            raise AuditWriteFailed(type(error).__name__) from error

    def finalize(self, event_id, **fields):
        unexpected = set(fields) - set(FIELDS)
        if unexpected:
            raise AuditWriteFailed(f"field(s) not in the audit schema: {sorted(unexpected)}")
        names = {f"#f{i}": name for i, name in enumerate(fields)}
        values = {f":v{i}": to_attr(value) for i, value in enumerate(fields.values())}
        expression = "SET " + ", ".join(f"#f{i} = :v{i}" for i in range(len(fields)))
        try:
            self._client.update_item(TableName=self._table, Key={"event_id": {"S": event_id}},
                                     UpdateExpression=expression, ExpressionAttributeNames=names,
                                     ExpressionAttributeValues=values, ConditionExpression="attribute_exists(event_id)")
        except Exception as error:  # noqa: BLE001
            raise AuditWriteFailed(type(error).__name__) from error


def log_operational(**fields):
    """Operational log line with allowlisted fields only — never events, bodies, questions, chunks or answers."""
    print(json.dumps({k: fields[k] for k in LOG_FIELDS if k in fields}, sort_keys=True))
