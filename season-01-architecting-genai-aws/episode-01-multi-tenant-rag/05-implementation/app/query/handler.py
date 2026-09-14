"""Query service: POST /ask. Runs the principle chain in order, and fails closed at every step.

    VERIFIED IDENTITY → TRUSTED TENANT CONTEXT → AUTHORISATION + TENANT CONSTRAINT → RETRIEVAL
    → OWNERSHIP VERIFICATION → AUDIT (before generation) → GENERATION → CITATION ALLOW-LIST
"""
import os
import time
import uuid

from query import model_client, prompt
from shared import audit, build_info, citations, http, ownership_verification, request_schema, retrieval_client
from shared import retrieval_scope, tenant_context
from shared.reason_codes import AUDIT_WRITE_FAILED, INTERNAL_ERROR, Denied
from shared.registry import Registry

ROUTE = "POST /ask"
NOT_FOUND_ANSWER = "I cannot find that in your organisation's documents."
_REGISTRY_CONFIG = {"connect_timeout": 1, "read_timeout": 1, "retries": {"max_attempts": 2}}
_clients = {}


def _client(name, config=None):
    key = (name, config is not None)
    if key not in _clients:
        import boto3  # imported lazily so component tests run without the AWS SDK
        from botocore.config import Config
        _clients[key] = boto3.client(name, config=Config(**config)) if config else boto3.client(name)
    return _clients[key]


def handler(event, context):
    started = time.monotonic()
    event_id = str(uuid.uuid4())
    record = audit.new_record(event_id, ROUTE, "ask", event, build_info.VARIANT)
    record["knowledge_base_id"] = os.environ["KNOWLEDGE_BASE_ID"]
    registry = Registry(_client("dynamodb", _REGISTRY_CONFIG), os.environ["REGISTRY_TABLE"])
    audit_log = audit.AuditLog(_client("dynamodb", _REGISTRY_CONFIG), os.environ["AUDIT_TABLE"])
    written = False
    try:
        # 1. Trusted tenant context from verified claims + registry (never from the request).
        ctx = tenant_context.resolve(event, registry, os.environ["APP_CLIENT_ID"], os.environ["TOKEN_ISSUER"])
        record.update(user_id=ctx.user_id, token_issuer=ctx.issuer, client_id=ctx.client_id, tenant_context=ctx.tenant_id)

        # 2. Allowlisted body: only "question".
        question = request_schema.parse_ask(event)
        record["question_length"] = len(question)

        # 3. PRIMARY CONTROL: authorisation decision + mandatory tenant constraint, built in one place.
        scoped = retrieval_scope.authorize_and_scope(ctx, "ask", question)
        record.update(constraint=retrieval_scope.constraint_record(scoped),
                      constraint_sha256=retrieval_scope.constraint_sha256(scoped))

        # 4. Retrieval, constrained during the search.
        chunks = retrieval_client.retrieve(_client("bedrock-agent-runtime"), os.environ["KNOWLEDGE_BASE_ID"], scoped)
        record["retrieved"] = [{"document_id": c.document_id, "owner_attribute": c.owner_attribute} for c in chunks]

        # 5. DEFENCE IN DEPTH: verify every retrieved chunk before generation (withhold everything on mismatch).
        result = ownership_verification.verify(ctx, chunks, registry)
        record.update(verification_outcome=result.outcome, discarded_count=result.discarded_count,
                      decision="ALLOW", reason_code="ALLOWED", status_code=200)

        # 6. Audit record written BEFORE generation; if it cannot be written, nothing is generated.
        try:
            audit_log.write_decision(record)
            written = True
        except audit.AuditWriteFailed as error:
            raise Denied(AUDIT_WRITE_FAILED, str(error)) from error

        # 7. Generation over verified chunks only, then the citation allow-list.
        if result.verified:
            labels, system, messages = prompt.build(question, result.verified)
            text, _usage = model_client.generate(_client("bedrock-runtime"), os.environ["GENERATION_MODEL_ID"],
                                                 system, messages)
            answer, cited = citations.build(text, labels)
        else:
            answer, cited = NOT_FOUND_ANSWER, []
        try:
            audit_log.finalize(event_id, outcome="ANSWERED", cited_document_ids=[c["document_id"] for c in cited],
                               latency_ms=audit.elapsed_ms(started))
        except audit.AuditWriteFailed as error:
            audit.log_operational(event_id=event_id, route=ROUTE, error_class="AUDIT_FINALIZE_FAILED", message=str(error))
        return http.response(200, {"answer": answer, "citations": cited, "event_id": event_id}, event_id)

    except Denied as refusal:
        return _refuse(refusal, record, audit_log, written, event_id, started)
    except Exception as error:  # noqa: BLE001 — unexpected failures are refusals too
        audit.log_operational(event_id=event_id, route=ROUTE, error_class=type(error).__name__)
        return _refuse(Denied(INTERNAL_ERROR, type(error).__name__), record, audit_log, written, event_id, started)


def _refuse(refusal, record, audit_log, written, event_id, started):
    reason = refusal.reason
    withheld = reason.code in ("OWNERSHIP_MISMATCH", "OWNERSHIP_LOOKUP_FAILED")
    outcome = "WITHHELD" if withheld else ("ERROR" if reason.status >= 500 else "DENIED")
    if reason.code == "OWNERSHIP_MISMATCH":
        record["verification_outcome"] = "OWNERSHIP_MISMATCH"
    elif reason.code == "OWNERSHIP_LOOKUP_FAILED":
        record["verification_outcome"] = "LOOKUP_FAILED"
    fields = {"decision": "DENY", "reason_code": reason.code, "failed_control": reason.failed_control,
              "outcome": outcome, "status_code": reason.status, "latency_ms": audit.elapsed_ms(started)}
    try:
        if written:
            audit_log.finalize(event_id, **fields)
        elif reason.code != "AUDIT_WRITE_FAILED":
            record.update(fields)
            audit_log.write_decision(record)
    except audit.AuditWriteFailed as error:
        audit.log_operational(event_id=event_id, route=ROUTE, error_class="AUDIT_WRITE_FAILED", message=str(error))
    audit.log_operational(event_id=event_id, route=ROUTE, reason_code=reason.code, status_code=reason.status,
                          latency_ms=fields["latency_ms"])
    return http.refusal(reason, event_id)
