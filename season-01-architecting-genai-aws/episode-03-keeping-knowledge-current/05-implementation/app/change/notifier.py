"""Change notifier (CTL-035, part 1; ADR-003).

    NOTIFICATIONS PROVIDE LOW-LATENCY CHANGE SIGNALS. THEY NEVER PROVE COMPLETENESS.

The records table's stream tells this function that an authoritative record changed. It does one small thing, quickly:

    write a PENDING entry for the document, then ask the applier to converge it.

Writing the pending entry FIRST is the point: from that moment the request path will not serve the document as current
(core/convergence.py), even though the expensive content work has not started. Safety does not wait for indexing.

What this function must never do:
  * advance a watermark — only a completed reconciliation pass may (ADR-003, ADR-007);
  * read or trust document text — status comes from the record (SEC-004);
  * treat "no notification" as "no change" — that is what reconciliation is for.
"""
import json
import os

from adapters.stores import ConvergenceStore, from_item
from core import convergence, record_state

_clients = {}


def _client(name):
    if name not in _clients:
        import boto3
        _clients[name] = boto3.client(name)
    return _clients[name]


def _record(image):
    """The authoritative record JSON from a stream image, or None when the image holds no record."""
    if not image:
        return None
    try:
        item = from_item(image)
    except (TypeError, KeyError, ValueError):
        return None
    raw = item.get("record")
    if not isinstance(raw, str):
        return None
    try:
        return json.loads(raw)
    except ValueError:
        return None


def _document_label(record):
    return (record or {}).get("document_label")


def changes(event):
    """Stream event → [(document_id, before RecordState or None, after RecordState or None, change_class)].

    History items (HISTORY#…) are versions kept for reconstruction, never a change in their own right.
    """
    result = []
    for entry in (event or {}).get("Records", []):
        image = entry.get("dynamodb") or {}
        after_record = _record(image.get("NewImage"))
        before_record = _record(image.get("OldImage"))
        keys = from_item(image.get("Keys") or {})
        document_id = keys.get("document_id") or (after_record or before_record or {}).get("document_id")
        if not isinstance(document_id, str) or document_id.startswith("HISTORY#"):
            continue
        after = record_state.parse(document_id, after_record) if after_record else None
        before = record_state.parse(document_id, before_record) if before_record else None
        change_class = convergence.change_class_for(before, after, _document_label(before_record),
                                                    _document_label(after_record))
        result.append((document_id, before, after, change_class))
    return result


def handler(event, context):
    return run(event, ConvergenceStore(_client("dynamodb"), os.environ["CONVERGENCE_TABLE"]),
               applier=os.environ.get("APPLIER_FUNCTION_NAME"), invoke=_invoke_applier)


def _invoke_applier(function_name, document_ids):
    _client("lambda").invoke(FunctionName=function_name, InvocationType="Event",
                             Payload=json.dumps({"document_ids": sorted(document_ids)}).encode())


def run(event, convergence_store, applier=None, invoke=None, now=None):
    """Write one pending entry per changed document, then ask the applier to converge them."""
    noticed_at = now or record_state.now_iso()
    noted = []
    for document_id, _before, after, change_class in changes(event):
        pending = convergence.Pending(document_id, change_class,
                                      after.version if after is not None else 0, noticed_at,
                                      detail=(after.status if after is not None else record_state.DELETED))
        convergence_store.put_pending(pending)
        noted.append(pending.item())
    if noted and applier and invoke:
        invoke(applier, [p["document_id"] for p in noted])
    report = {"record_type": "CHANGE_NOTIFICATION", "noticed_at": noticed_at, "pending": noted,
              "note": "a notification never advances a watermark; completeness is established by reconciliation only"}
    print(json.dumps({"stage": "notify", "documents": [p["document_id"] for p in noted]}, sort_keys=True))
    return report
