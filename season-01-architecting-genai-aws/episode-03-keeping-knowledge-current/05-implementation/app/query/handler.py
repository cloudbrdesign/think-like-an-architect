"""Query function: POST /ask. One deployment unit; each step below is its own module.

    1 identity / trusted request context   query/trusted_context.py
    2 authorization decision                query/policy_decision.py      no authoritative current grants → stop
    3 tier selection                        core/tier_selection.py        D3 layer 1: blast-radius reduction
    4 constraint construction               core/constraints.py           D3 layer 2: requester eligibility
    5 retrieval gateway                     query/retrieval_gateway.py    the only knowledge-base caller
    6 authority + convergence + verification core/verification.py         any mismatch → withhold everything
    7 relevance (answer quality only)       core/relevance.py
    8 generation                            query/generation.py
    9 response handling                     query/response.py             uniform non-answer
   10 audit                                 core/audit_record.py          one content-free record per request

Episode 03 changes step 6 and only step 6. The authoritative record read that Episode 02 already made now also carries
status, effective version and supersession (ADR-001), and the request path reads the convergence view for the candidate
documents (ADR-002). A candidate is used only when it is KNOWN_CURRENT:

    superseded / withdrawn / deleted   → WITHHELD_NOT_CURRENT
    a newer effective version pending  → WITHHELD_PENDING_CHANGE      (known stale is not current)
    state cannot be established        → WITHHELD_UNKNOWN_STATE
    convergence store unreadable       → WITHHELD_CONVERGENCE_UNAVAILABLE for safety-critical content

Every refusal is a normal, audited outcome. If the audit record cannot be written, no answer is released.
"""
import json
import os
import time
import uuid
from dataclasses import dataclass

from adapters import build_info
from core import audit_record, constraints, convergence, freshness, relevance, tier_selection, verification
from core.reason_codes import (ANSWERED, INTERNAL_ERROR, NO_ELIGIBLE_CONTENT, NO_RELEVANT_CONTENT,
                               WITHHELD_CLASSIFICATION_UNAVAILABLE, WITHHELD_CONVERGENCE_UNAVAILABLE,
                               WITHHELD_NOT_CURRENT, WITHHELD_PENDING_CHANGE, WITHHELD_UNKNOWN_STATE,
                               WITHHELD_VERIFICATION_MISMATCH, Refusal)
from query import generation, policy_decision, response, retrieval_gateway, trusted_context

_clients = {}   # AWS SDK clients only — never grants, records, convergence state or results

CURRENCY_OUTCOME = {verification.NOT_CURRENT: WITHHELD_NOT_CURRENT,
                    verification.PENDING_CHANGE: WITHHELD_PENDING_CHANGE,
                    verification.UNKNOWN_STATE: WITHHELD_UNKNOWN_STATE}


@dataclass
class Services:
    grants: object
    records: object
    convergence: object
    audit: object
    agent_runtime: object
    bedrock_runtime: object
    knowledge_base_ids: dict
    model_id: str
    min_relevance: float
    deployment: str


def _client(name):
    if name not in _clients:
        import boto3
        from botocore.config import Config
        timeouts = {"dynamodb": (2, 3)}.get(name, (3, 30))
        _clients[name] = boto3.client(name, config=Config(connect_timeout=timeouts[0], read_timeout=timeouts[1],
                                                          retries={"max_attempts": 2}))
    return _clients[name]


def services_from_environment():
    from adapters.stores import AuditStore, ConvergenceStore, GrantsStore, RecordsStore
    env = os.environ
    return Services(grants=GrantsStore(_client("dynamodb"), env["AUTHORIZATION_TABLE"]),
                    records=RecordsStore(_client("dynamodb"), env["RECORDS_TABLE"]),
                    convergence=ConvergenceStore(_client("dynamodb"), env["CONVERGENCE_TABLE"]),
                    audit=AuditStore(_client("dynamodb"), env["AUDIT_TABLE"]),
                    agent_runtime=_client("bedrock-agent-runtime"), bedrock_runtime=_client("bedrock-runtime"),
                    knowledge_base_ids={tier_selection.SHARED: env["SHARED_KNOWLEDGE_BASE_ID"],
                                        tier_selection.RESTRICTED_TIER: env["RESTRICTED_KNOWLEDGE_BASE_ID"]},
                    model_id=env["GENERATION_MODEL_ID"], min_relevance=float(env["RELEVANCE_MIN_SCORE"]),
                    deployment=env["DEPLOYMENT_NAME"])


def _ms(started):
    return int((time.monotonic() - started) * 1000)


def log(**fields):
    """Operational log line: identifiers, stage, outcome and timings only — never bodies, questions or text."""
    allowed = ("request_id", "stage", "outcome", "failing_control", "detail", "latency_ms")
    print(json.dumps({k: fields[k] for k in allowed if k in fields}, sort_keys=True))


def _currency_outcome(result):
    """The outcome for a withholding caused by currency, in order of consequence."""
    reasons = result.currency_reasons
    for reason in (verification.NOT_CURRENT, verification.UNKNOWN_STATE, verification.PENDING_CHANGE):
        if reason in reasons:
            return CURRENCY_OUTCOME[reason]
    return None


def handler(event, context):
    return handle(event, services_from_environment())


def handle(event, services):
    started = time.monotonic()
    request_id = str(uuid.uuid4())
    record = audit_record.new(request_id, services.deployment, build_info.VARIANT)
    body = None
    try:
        # 1 identity
        ctx = trusted_context.resolve(event)
        record["requester_sub"] = ctx.requester_sub
        question = trusted_context.question(event)

        # 2 authorization decision (fresh, consistent reads; fail closed) — Episode 02, unchanged
        step = time.monotonic()
        decision, employee_id = policy_decision.decide(ctx, services.grants)
        record["latency_ms"]["decision"] = _ms(step)
        record["employee_id"] = employee_id
        record["decision"] = {"status": decision.status, "hr_version": decision.hr_version,
                              "grants_version": decision.grants_version, "domains": list(decision.domains),
                              "cases": list(decision.cases)}
        if not decision.allowed:
            raise Refusal(decision.outcome)

        # 3 tier selection and 4 constraint construction — Episode 02, unchanged
        tiers = tier_selection.select_tiers(decision)
        queries = constraints.build_tier_queries(decision, tiers)
        record["constraints"] = [{"tier": q.tier, "sha256": q.filter_sha256, "bytes": q.filter_bytes} for q in queries]

        # 5 retrieval gateway (the constraint is evaluated during the search)
        step = time.monotonic()
        chunks = retrieval_gateway.retrieve(services.agent_runtime, services.knowledge_base_ids, question, queries,
                                            record["tiers_called"])
        record["latency_ms"]["retrieval"] = _ms(step)
        record["retrieval"] = [audit_record.retrieval_entry(c) for c in chunks]
        if not chunks:
            raise Refusal(NO_ELIGIBLE_CONTENT)

        # 6a the authoritative records for the candidates (label, scope, version — and now status and supersession)
        step = time.monotonic()
        document_ids = sorted({c.document_id for c in chunks if isinstance(c.document_id, str)})
        try:
            records = services.records.read_records(document_ids)
        except Exception as error:  # noqa: BLE001
            record["verification"] = {"status": "UNAVAILABLE", "mismatches": []}
            raise Refusal(WITHHELD_CLASSIFICATION_UNAVAILABLE, type(error).__name__) from error

        # 6b the convergence view: what is pending, and what completeness has been proven
        view = services.convergence.read_view(document_ids)
        last_reconciliation = None
        try:
            last_reconciliation = services.convergence.last_reconciliation()
        except Exception:  # noqa: BLE001 — a missing reconciliation record is itself evidence (overdue)
            pass
        claim = freshness.claim(view.watermarks, view.pending, last_reconciliation=last_reconciliation)
        conservative = any(freshness.conservative_mode(claim, c) for c in convergence.SAFETY_CRITICAL_CLASSES)
        record["convergence"] = {"available": view.available,
                                 "document_states": {}, "pending": [p.item() for p in view.pending.values()]}
        record["freshness"] = audit_record.freshness_entry(claim, conservative)
        record["latency_ms"]["convergence"] = _ms(step)
        if conservative:
            # ADR-002: the watermark is the third input to serving, and a watermark older than its target puts the
            # safety-critical classes into conservative mode. ADR-007: safety-critical content is then withheld rather
            # than served on an unprovable claim. Note the direction — this machinery can only ever WITHHOLD. It never
            # makes content available that eligibility would have refused (SEC-001 is inherited unchanged).
            raise Refusal(WITHHELD_CONVERGENCE_UNAVAILABLE if not view.available else WITHHELD_UNKNOWN_STATE,
                          "CONVERGENCE_UNREADABLE" if not view.available else "COMPLETENESS_NOT_PROVEN")

        # 6c one judgement per chunk: currency first, then the Episode 02 checks
        step = time.monotonic()
        result = verification.verify(decision, chunks, records, view)
        record["latency_ms"]["verification"] = _ms(step)
        record["convergence"]["document_states"] = dict(result.states or {})
        record["verification"] = {"status": result.status,
                                  "mismatches": [{"chunk_id": c, "reason": r} for c, r in result.mismatches],
                                  "record_versions": {d: r["version"] for d, r in records.items()
                                                      if isinstance(r, dict) and isinstance(r.get("version"), int)}}
        if result.status != verification.PASS:
            raise Refusal(_currency_outcome(result) or WITHHELD_VERIFICATION_MISMATCH, result.mismatches[0][1])

        # 7 relevance — answer quality only; it sees verified chunks and nothing about the requester
        kept, omitted = relevance.apply(result.verified, services.min_relevance)
        record["relevance"] = {"min_score": services.min_relevance, "kept": [c.chunk_id for c in kept],
                               "omitted": [c.chunk_id for c in omitted]}
        if not kept:
            raise Refusal(NO_RELEVANT_CONTENT)

        # 8 generation over verified, current, relevant chunks only
        step = time.monotonic()
        record["generation"] = {"invoked": True, "model_id": services.model_id}
        text, usage = generation.generate(services.bedrock_runtime, services.model_id, question, kept)
        record["latency_ms"]["generation"] = _ms(step)
        record["generation"].update(input_tokens=usage.get("inputTokens"), output_tokens=usage.get("outputTokens"))
        if text.strip().rstrip(".") == response.UNIFORM_NO_ANSWER.rstrip("."):
            raise Refusal(NO_RELEVANT_CONTENT, "sources did not answer")      # no citations for a non-answer

        # 9 response
        body = response.answered(request_id, text, response.citations(kept, records))
        record["outcome"] = ANSWERED
    except Refusal as refusal:
        record.update(outcome=refusal.outcome, failing_control=refusal.failing_control, detail=refusal.detail or None)
    except Exception as error:  # noqa: BLE001 — unexpected failures are refusals too
        record.update(outcome=INTERNAL_ERROR, detail=type(error).__name__)

    # 10 audit — one content-free record per request; no record, no answer
    record["latency_ms"]["total"] = _ms(started)
    try:
        services.audit.put(audit_record.validate(record))
    except Exception as error:  # noqa: BLE001
        log(request_id=request_id, stage="audit", outcome="AUDIT_WRITE_FAILED", detail=type(error).__name__)
        return response.uniform(request_id)
    log(request_id=request_id, stage="complete", outcome=record["outcome"], failing_control=record["failing_control"],
        latency_ms=record["latency_ms"]["total"])
    return body if record["outcome"] == ANSWERED else response.uniform(request_id)
