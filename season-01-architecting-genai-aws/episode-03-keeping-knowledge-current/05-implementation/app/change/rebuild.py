"""Repair and rebuild (CTL-033; ADR-008).

    BUILD A COMPLETE GENERATION. VERIFY IT. THEN SWITCH.

Targeted repair is the normal mechanism: reconciliation finds a difference, the applier converges that document. This
function is the exceptional path — when derived state for a set of documents can no longer be trusted, it rebuilds each
document's generation from authority, verifies it, promotes it and retires the old one.

It uses the same ordered, idempotent applier path, so a rebuild can never move a document backwards, and the serving
generation stays available if a replacement fails verification.

Rebuild is NOT the normal way to propagate change. The report says so, and the validation theme (VT-9) demonstrates a
rebuild while answering continues — not a rebuild as the freshness mechanism.
"""
import json
import os
import time
import uuid

from change import applier
from core import record_state
from core.audit_record import SCHEMA

_clients = {}


def _client(name):
    if name not in _clients:
        import boto3
        _clients[name] = boto3.client(name)
    return _clients[name]


def handler(event, context):
    return run(event, **applier.services_from_environment())


def run(event, records, source, storage, convergence_store, agent, knowledge_bases, deployment, audit=None,
        sleep=time.sleep, now=None):
    """`event`: {"document_ids": [...]} or {"all": true}. Each document is rebuilt from the authoritative record."""
    started_at = now or record_state.now_iso()
    document_ids = [d for d in (event or {}).get("document_ids", []) if isinstance(d, str)]
    if (event or {}).get("all"):
        document_ids = sorted(records.export())
    report = {"record_type": "REBUILD", "deployment": deployment, "started_at": started_at, "rebuilt": [],
              "failed": [], "unchanged": [],
              "note": "generation rebuild is the exceptional repair path, not the change-propagation mechanism"}
    current = records.read_records(document_ids) if document_ids else {}
    for document_id in sorted(document_ids):
        record = current.get(document_id)
        state = record_state.parse(document_id, record) if record is not None else None
        if state is None or not state.servable:
            report["unchanged"].append({"document_id": document_id,
                                        "reason": "not in force" if state else "no authoritative record"})
            continue
        try:
            outcome = applier._build_and_switch(document_id, record, state, source, storage, convergence_store,  # noqa: SLF001
                                                agent, knowledge_bases, sleep)
            report["rebuilt"].append(outcome)
        except Exception as error:  # noqa: BLE001 — the previous generation keeps serving
            # The same failure record as the applier's: a rebuild that fails must be as diagnosable as a change that
            # fails, or the exceptional repair path becomes the one place an operator cannot see into.
            report["failed"].append({
                **applier._failure(document_id, error, record,  # noqa: SLF001
                                   applier._reflected_quietly(convergence_store, document_id)),  # noqa: SLF001
                "serving_generation_kept": True})
    report["completed_at"] = record_state.now_iso()
    if audit is not None:
        audit.put({"request_id": f"rbd-{uuid.uuid4()}", "schema": SCHEMA, "timestamp": report["completed_at"],
                   **report})
    print(json.dumps({"stage": "rebuild", "rebuilt": len(report["rebuilt"]), "failed": len(report["failed"]),
                      "unchanged": len(report["unchanged"])}, sort_keys=True))
    return report
