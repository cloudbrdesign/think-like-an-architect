"""Reconciliation: the only mechanism that establishes completeness (CTL-035; ADR-003, ADR-007).

    EVENT DELIVERY TELLS US ABOUT THE CHANGES WE RECEIVED.
    RECONCILIATION TELLS US ABOUT THE CHANGES WE WERE NEVER TOLD ABOUT.

One pass compares the AUTHORITATIVE export with what derived state reflects, and produces three sets:

    missing     authority has a version derived state does not reflect   → pending + repair
    extra       derived state reflects a document authority no longer has → pending + repair (deletion)
    divergent   the reflected status or version disagrees                 → pending + repair

Only a pass that completes over every record may advance a class watermark, and it advances it to the moment the pass
STARTED — never to "now", because changes made during the pass may not have been seen. A pass that fails leaves the
watermark where it was: the age of that watermark is then the honest statement of what the system knows.

FX-3 disables this function while notifications are dropped. The pipeline still looks healthy; the watermark stops
moving, and the difference between "every received event was processed" and "every authoritative change is accounted
for" becomes visible.
"""
import dataclasses
import json
import os
import uuid

from adapters.stores import ConvergenceStore, RecordsStore
from core import convergence, freshness, record_state

_clients = {}


def _client(name):
    if name not in _clients:
        import boto3
        _clients[name] = boto3.client(name)
    return _clients[name]


def handler(event, context):
    env = os.environ
    return run(event,
               records=RecordsStore(_client("dynamodb"), env["RECORDS_TABLE"]),
               convergence_store=ConvergenceStore(_client("dynamodb"), env["CONVERGENCE_TABLE"]),
               applier=env.get("APPLIER_FUNCTION_NAME"), invoke=_invoke_applier, emit=_raise_breach_alert,
               deployment=env["DEPLOYMENT_NAME"])


def _raise_breach_alert(deployment, breached_total, breaches):
    """The escalation alert (OPS-001, ADR-007 §3): one structured line on this function's OWN log group, turned into
    a CloudWatch metric by a metric filter and watched by a CloudWatch alarm.

    Metric and alarm as ruled — but raised through the log group the reconciler already writes to, so the role needs
    no new permission. `cloudwatch:PutMetricData` admits no resource-level permission, so calling it directly needs
    `Resource: "*"` in an application role; a static rule forbids that outright, and no alert is worth weakening a
    control to deliver.

    Printed on EVERY completed pass, including zero, so the alarm returns to OK once the breach is repaired instead
    of latching on for ever. The affected identifiers travel in this same line: as a metric dimension they would
    create one metric per document and bound nothing. Identifiers, classes and counts only — never content.
    """
    print(json.dumps({"stage": "escalation", "deployment": deployment or "unknown",
                      "breached_total": int(breached_total), "window_breaches": breaches}, sort_keys=True))


def _escalate(convergence_store, pending, at, emit, deployment):
    """Escalate every change that has outlived its class's window: RAISE THE ALERT, THEN mark the entry.

    The order is load-bearing. Emitting first means a failure to persist can only cause the same alert to be raised
    again next pass. Persisting first would mark a change escalated for an alert that was never actually raised, and
    nothing would ever raise it again — the silent loss FRS-004 exists to prevent, reintroduced by the escalation
    itself. An emit that fails therefore marks nothing.
    """
    breaches = freshness.window_breaches(pending, now=at)
    breached = sorted({d for ids in breaches.values() for d in ids})
    newly = [d for d in breached if not pending[d].escalated_at]
    record = {"breaches": breaches, "breached_total": len(breached), "newly_escalated": newly, "emitted": False}
    if emit is None:
        return record
    try:
        emit(deployment, len(breached), breaches)
        record["emitted"] = True
    except Exception as error:  # noqa: BLE001 — an alert that was never raised must NOT be recorded as escalated
        record["emit_error"] = {"error": type(error).__name__,
                                "message": " ".join(str(error).split())[:200] or None}
        return record
    if newly:
        # RE-READ rather than writing back the snapshot this pass began with. The applier runs BETWEEN that snapshot
        # and this write — the repair loop invokes it — and it records genuine failed attempts on the same entry.
        # Writing the stale copy back erased them, losing precisely the retry evidence FRS-004 requires ("recorded as
        # failed, retried and escalated"). An entry that CONVERGED in the meantime is not re-created either: a
        # resurrected incident would later escalate a change that had in fact been applied.
        current = convergence_store.pending_all()
        for document_id in newly:
            entry = current.get(document_id)
            if entry is not None:
                convergence_store.put_pending(dataclasses.replace(entry, escalated_at=at))
    return record


def _invoke_applier(function_name, document_ids):
    _client("lambda").invoke(FunctionName=function_name, InvocationType="Event",
                             Payload=json.dumps({"document_ids": sorted(document_ids)}).encode())


def compare(export, reflected):
    """Pure comparison: (missing, extra, divergent) as lists of (document_id, detail)."""
    missing, extra, divergent = [], [], []
    for document_id in sorted(export):
        state = record_state.parse(document_id, export[document_id])
        current = reflected.get(document_id)
        if current is None:
            if state.servable:
                missing.append((document_id, {"authoritative_version": state.version, "reflected": None}))
            continue
        reflected_version = int(current.get("version") or 0)
        reflected_status = current.get("status")
        if state.servable and reflected_version != state.version:
            divergent.append((document_id, {"authoritative_version": state.version,
                                            "reflected_version": reflected_version}))
        elif not state.servable and reflected_status != record_state.DELETED:
            divergent.append((document_id, {"authoritative_status": state.status,
                                            "reflected_status": reflected_status}))
    for document_id in sorted(reflected):
        if document_id not in export and reflected[document_id].get("status") != record_state.DELETED:
            extra.append((document_id, {"authoritative": None,
                                        "reflected_version": int(reflected[document_id].get("version") or 0)}))
    return missing, extra, divergent


def run(event, records, convergence_store, applier=None, invoke=None, deployment=None, now=None, emit=None):
    """One reconciliation pass. `event` may name change classes; by default every class is reconciled."""
    started_at = now or record_state.now_iso()
    run_id = (event or {}).get("run_id") or f"rec-{uuid.uuid4().hex[:12]}"
    classes = [c for c in (event or {}).get("change_classes", convergence.CHANGE_CLASSES)
               if c in convergence.CHANGE_CLASSES]
    summary = {"run_id": run_id, "deployment": deployment, "started_at": started_at, "completed_at": None,
               "change_classes": classes, "documents_compared": 0, "missing": [], "extra": [], "divergent": [],
               "repairs_requested": [], "advanced": [], "note":
               "a watermark advances only through a completed pass, and only to the moment the pass started"}
    try:
        export = records.export()
        reflected = convergence_store.reflected_all()
    except Exception as error:  # noqa: BLE001 — an incomplete pass proves nothing and advances nothing
        # `failed` stays the bare class name: it is the recorded contract callers already read. The diagnosis goes
        # beside it, because "RuntimeError" alone cannot tell an operator which read failed or why.
        summary["failed"] = type(error).__name__
        summary["failure"] = {"error": type(error).__name__, "stage": "export_and_compare",
                              "message": " ".join(str(error).split())[:200] or None,
                              "code": ((getattr(error, "response", None) or {}).get("Error", {}).get("Code")
                                       if isinstance(getattr(error, "response", None), dict) else None),
                              "operation": getattr(error, "operation_name", None),
                              "at": record_state.now_iso()}
        convergence_store.put_reconciliation(run_id, summary)
        print(json.dumps({"stage": "reconcile", "run_id": run_id, "outcome": "FAILED"}, sort_keys=True))
        return summary

    missing, extra, divergent = compare(export, reflected)
    summary["documents_compared"] = len(set(export) | set(reflected))
    summary["missing"] = [{"document_id": d, **detail} for d, detail in missing]
    summary["extra"] = [{"document_id": d, **detail} for d, detail in extra]
    summary["divergent"] = [{"document_id": d, **detail} for d, detail in divergent]

    # Read before writing: an entry's `noticed_at` is the moment the change was FIRST noticed, and this pass must
    # not move it. Documents already pending from delivery count toward a breach too, so they are carried along.
    existing = convergence_store.pending_all()
    resulting = dict(existing)

    repairs = sorted({d for d, _ in missing + extra + divergent})
    for document_id in repairs:
        state = record_state.parse(document_id, export[document_id]) if document_id in export else None
        change_class = (convergence.change_class_for(None, state) if state is not None else convergence.DELETION)
        prior = existing.get(document_id)
        # THE CLOCK MUST NOT RESET. Writing `started_at` on every pass made a change that had been diverging for
        # hours look as though it had just been noticed: `oldest_pending_age_seconds` fell back to 0 each time, so no
        # class could ever leave its window, no breach could be raised, and an unrepairable change stayed invisible
        # for ever while reconciliation reported success (FRS-004, FRS-008, ADR-007 §3). The entry keeps the moment
        # it was first noticed, and its accounting, until it converges and is cleared.
        # THE INCIDENT IS NOT RECLASSIFIED. Reconciliation observes a DIFFERENCE, never the event that caused it:
        # it holds no "before" record and no labels, so `change_class_for(None, state)` can only ever return
        # deletion, supersede_withdraw or new_version — a reclassification is structurally unreachable here.
        # Overwriting an existing entry therefore replaced a well-informed classification with a strictly less
        # informed one, and a `reclassify_up` incident (safety-critical, zero-second window) silently became
        # `new_version` (not safety-critical, four hours). That did not merely lose the alert: `conservative_mode`
        # consults only SAFETY_CRITICAL_CLASSES, so the request path went from WITHHOLDING to SERVING.
        # ADR-007 requires that each difference "became a pending entry or a repair" — an entry that already exists
        # satisfies it. So the class is fixed when the incident is CREATED and preserved until it converges; a
        # recurrence after convergence is a new incident and is classified afresh.
        incident_class = prior.change_class if prior else change_class
        entry = convergence.Pending(document_id, incident_class, state.version if state else 0,
                                    prior.noticed_at if prior else started_at, detail="RECONCILIATION_DRIFT",
                                    attempts=prior.attempts if prior else 0,
                                    last_attempt_at=prior.last_attempt_at if prior else None,
                                    escalated_at=prior.escalated_at if prior else None)
        convergence_store.put_pending(entry)
        resulting[document_id] = entry
    if repairs and applier and invoke:
        invoke(applier, repairs)
    summary["repairs_requested"] = repairs

    summary["completed_at"] = record_state.now_iso()
    # Evaluated at the moment the pass STARTED, never at wall-clock "now" — the same rule the watermark follows two
    # lines below. Reading the clock here instead made every breach decision depend on when the code happened to run
    # rather than on the pass's own logical time.
    summary["escalation"] = _escalate(convergence_store, resulting, started_at, emit, deployment)
    for change_class in classes:
        convergence_store.advance_watermark(change_class, started_at, run_id, summary["completed_at"],
                                            summary["documents_compared"])
        summary["advanced"].append(change_class)
    convergence_store.put_reconciliation(run_id, summary)
    # OPS-001 / ADR-007 §3: the alert names the CLASS AND THE AFFECTED IDENTIFIERS. Identifiers and counts only.
    print(json.dumps({"stage": "reconcile", "run_id": run_id, "compared": summary["documents_compared"],
                      "missing": len(missing), "extra": len(extra), "divergent": len(divergent),
                      "advanced_through": started_at, "window_breaches": summary["escalation"]["breaches"],
                      "newly_escalated": summary["escalation"]["newly_escalated"],
                      "alert_emitted": summary["escalation"]["emitted"]}, sort_keys=True))
    return summary
