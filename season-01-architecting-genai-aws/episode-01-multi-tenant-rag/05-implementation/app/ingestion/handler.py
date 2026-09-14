"""Ingestion service: POST /documents · GET /documents/{document_id} · DELETE /documents/{document_id}.

Ownership comes from the trusted tenant context, never from the caller. Another tenant's document is
indistinguishable from a document that does not exist.
"""
import os
import time
import uuid

from shared import audit, build_info, http, ownership, request_schema, tenant_context
from shared.reason_codes import (AUDIT_WRITE_FAILED, DOCUMENT_NOT_FOUND_FOR_TENANT, INGESTION_ATTRIBUTION_CONFLICT,
                                 INTERNAL_ERROR, Denied)
from shared.registry import Registry

_CONFIG = {"connect_timeout": 1, "read_timeout": 2, "retries": {"max_attempts": 2}}
_clients = {}


def _client(name, config=None):
    key = (name, config is not None)
    if key not in _clients:
        import boto3  # imported lazily so component tests run without the AWS SDK
        from botocore.config import Config
        _clients[key] = boto3.client(name, config=Config(**config)) if config else boto3.client(name)
    return _clients[key]


def _env():
    return {k: os.environ[k] for k in ("REGISTRY_TABLE", "AUDIT_TABLE", "DOCUMENT_BUCKET", "KNOWLEDGE_BASE_ID",
                                       "DATA_SOURCE_ID", "APP_CLIENT_ID", "TOKEN_ISSUER")}


def handler(event, context):
    started = time.monotonic()
    event_id = str(uuid.uuid4())
    route = event.get("routeKey", "")
    action = {"POST /documents": "upload", "GET /documents/{document_id}": "open",
              "DELETE /documents/{document_id}": "delete"}.get(route, "unknown")
    env = _env()
    record = audit.new_record(event_id, route, action, event, build_info.VARIANT)
    registry = Registry(_client("dynamodb", _CONFIG), env["REGISTRY_TABLE"])
    audit_log = audit.AuditLog(_client("dynamodb", _CONFIG), env["AUDIT_TABLE"])
    try:
        ctx = tenant_context.resolve(event, registry, env["APP_CLIENT_ID"], env["TOKEN_ISSUER"])
        record.update(user_id=ctx.user_id, token_issuer=ctx.issuer, client_id=ctx.client_id, tenant_context=ctx.tenant_id)
        if action == "upload":
            status, body, outcome = _upload(event, ctx, env, registry, record)
        elif action == "open":
            status, body, outcome = _open(event, ctx, env, registry, record)
        elif action == "delete":
            status, body, outcome = _delete(event, ctx, env, registry, record)
        else:
            raise Denied(DOCUMENT_NOT_FOUND_FOR_TENANT, "unknown route")
        record.update(decision="ALLOW", reason_code="ALLOWED", outcome=outcome, status_code=status,
                      latency_ms=audit.elapsed_ms(started))
        try:
            audit_log.write_decision(record)
        except audit.AuditWriteFailed as error:
            # Fail loudly: the caller is told the request is not confirmed, and the gap is in the operational log.
            audit.log_operational(event_id=event_id, route=route, error_class="AUDIT_WRITE_FAILED", message=str(error))
            return http.refusal(AUDIT_WRITE_FAILED, event_id)
        return http.response(status, {**body, "event_id": event_id}, event_id)
    except Denied as refusal:
        return _refuse(refusal, record, audit_log, event_id, route, started)
    except Exception as error:  # noqa: BLE001
        audit.log_operational(event_id=event_id, route=route, error_class=type(error).__name__)
        return _refuse(Denied(INTERNAL_ERROR, type(error).__name__), record, audit_log, event_id, route, started)


def _upload(event, ctx, env, registry, record):
    title, content = request_schema.parse_upload(event)            # refuses owner, tenant or ID fields
    document_id = str(uuid.uuid4())                                  # server-generated identifier
    key = ownership.storage_key(ctx.tenant_id, document_id)          # server-derived storage location
    record["document_id"] = document_id
    _client("s3").put_object(Bucket=env["DOCUMENT_BUCKET"], Key=key, Body=content.encode("utf-8"),
                             ContentType="text/markdown; charset=utf-8")
    store = ownership.OwnershipStore(_client("dynamodb", _CONFIG), env["REGISTRY_TABLE"])
    store.create_document(ctx, document_id, title, key)            # ownership record: owner = context tenant
    return _attribute_and_index(ctx, env, registry, store, document_id, key, title)


def _attribute_and_index(ctx, env, registry, store, document_id, key, title):
    stored = registry.get_document(document_id)                      # read back what was actually recorded
    attributes = ownership.index_attributes(ctx.tenant_id, document_id)
    try:
        ownership.attribution_gate(ctx, stored, key, attributes)
    except ownership.AttributionConflict as conflict:
        # Quarantine: never index. If even the quarantine mark cannot be written, the document is still not indexed.
        try:
            store.set_status(document_id, (stored or {}).get("owner", ctx.tenant_id), ownership.QUARANTINED,
                             (ownership.RECEIVED,))
        except ownership.OwnershipConflict:
            pass
        raise Denied(INGESTION_ATTRIBUTION_CONFLICT, str(conflict)) from conflict
    ownership.index_document(_client("bedrock-agent"), env["KNOWLEDGE_BASE_ID"], env["DATA_SOURCE_ID"],
                             env["DOCUMENT_BUCKET"], key, attributes, document_id)
    store.set_status(document_id, ctx.tenant_id, ownership.INDEXING, (ownership.RECEIVED,))
    return 202, {"document_id": document_id, "title": title, "status": ownership.INDEXING}, "UPLOADED"


def _owned_record(event, ctx, registry, record):
    document_id = request_schema.path_document_id(event)
    record["document_id"] = document_id
    found = registry.get_document(document_id)
    if found is None or found.get("owner") != ctx.tenant_id:
        raise Denied(DOCUMENT_NOT_FOUND_FOR_TENANT, "unknown document or another tenant's document")
    return found


def _open(event, ctx, env, registry, record):
    found = _owned_record(event, ctx, registry, record)
    store = ownership.OwnershipStore(_client("dynamodb", _CONFIG), env["REGISTRY_TABLE"])
    status = found["status"]
    agent = _client("bedrock-agent")
    if status == ownership.INDEXING:
        index = ownership.index_status(agent, env["KNOWLEDGE_BASE_ID"], env["DATA_SOURCE_ID"], found["document_id"])
        if index == "INDEXED":
            store.set_status(found["document_id"], ctx.tenant_id, ownership.AVAILABLE, (ownership.INDEXING,))
            status = ownership.AVAILABLE
        elif index in ("FAILED", "IGNORED"):
            store.set_status(found["document_id"], ctx.tenant_id, ownership.FAILED, (ownership.INDEXING,))
            status = ownership.FAILED
    elif status == ownership.DELETING:
        if ownership.index_status(agent, env["KNOWLEDGE_BASE_ID"], env["DATA_SOURCE_ID"], found["document_id"]) == "NOT_FOUND":
            store.set_status(found["document_id"], ctx.tenant_id, ownership.DELETED, (ownership.DELETING,))
            status = ownership.DELETED
    body = {"document_id": found["document_id"], "title": found.get("title", ""), "status": status}
    if status == ownership.AVAILABLE:
        obj = _client("s3").get_object(Bucket=env["DOCUMENT_BUCKET"], Key=found["s3_key"])
        body["content"] = obj["Body"].read().decode("utf-8")
    return 200, body, "OPENED"


def _delete(event, ctx, env, registry, record):
    found = _owned_record(event, ctx, registry, record)
    if found["status"] in (ownership.DELETING, ownership.DELETED):
        return 202, {"document_id": found["document_id"], "status": found["status"]}, "DELETING"
    store = ownership.OwnershipStore(_client("dynamodb", _CONFIG), env["REGISTRY_TABLE"])
    store.set_status(found["document_id"], ctx.tenant_id, ownership.DELETING,
                     (ownership.RECEIVED, ownership.INDEXING, ownership.AVAILABLE, ownership.QUARANTINED, ownership.FAILED))
    ownership.delete_from_index(_client("bedrock-agent"), env["KNOWLEDGE_BASE_ID"], env["DATA_SOURCE_ID"],
                                found["document_id"])
    _client("s3").delete_object(Bucket=env["DOCUMENT_BUCKET"], Key=found["s3_key"])
    return 202, {"document_id": found["document_id"], "status": ownership.DELETING}, "DELETING"


def _refuse(refusal, record, audit_log, event_id, route, started):
    reason = refusal.reason
    outcome = {"INGESTION_ATTRIBUTION_CONFLICT": "QUARANTINED"}.get(reason.code,
                                                                   "ERROR" if reason.status >= 500 else "DENIED")
    record.update(decision="DENY", reason_code=reason.code, failed_control=reason.failed_control, outcome=outcome,
                  status_code=reason.status, latency_ms=audit.elapsed_ms(started))
    try:
        audit_log.write_decision(record)
    except audit.AuditWriteFailed as error:
        audit.log_operational(event_id=event_id, route=route, error_class="AUDIT_WRITE_FAILED", message=str(error))
    audit.log_operational(event_id=event_id, route=route, reason_code=reason.code, status_code=reason.status,
                          latency_ms=record["latency_ms"])
    return http.refusal(reason, event_id)
