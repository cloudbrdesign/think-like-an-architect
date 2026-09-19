"""Change operations and convergence observations (operator credentials — PRIVILEGED).

The harness plays the part of the records system's operators: it changes an AUTHORITATIVE record and then watches what
the derived system does about it. Everything here goes through an interface a real operator has — the records table,
the change functions, the stream's on/off switch — so no test can prove a property by writing derived state itself.

Reading, by contrast, is unrestricted: the convergence table is scanned directly, because evidence about what the
system knew must not depend on the system agreeing to tell us.

Note the ordering consequence of AB-1: a deployment that has never completed a reconciliation pass cannot prove
completeness, so it withholds. `load` therefore reconciles once after the fixtures are in place, and every experiment
that stops reconciliation records that the withholding which follows is the architecture working, not a defect.
"""
import json
import random
import time
from datetime import datetime, timezone

from harness import common  # noqa: F401 — puts the application on the import path
from adapters.stores import ConvergenceStore as CS, from_item, to_item
from core import record_state as rs

PREFIXES = {"pending": CS.PENDING, "reflected": CS.REFLECTED, "generation": CS.GENERATION,
            "watermark": CS.WATERMARK, "reconciliation": CS.RECONCILIATION, "deletion": CS.DELETION}


# ── the authoritative records system (operator writes) ──────────────────────────────────────────────────────────────
def record(target, document_id):
    """The current authoritative record, or None when authority no longer holds the document."""
    item = target.client("dynamodb").get_item(TableName=target.outputs["RecordsTable"], ConsistentRead=True,
                                              Key={"document_id": {"S": document_id}}).get("Item")
    return json.loads(from_item(item)["record"]) if item else None


def put_record(target, value):
    """Write an authoritative record, keeping the version history used for reconstruction."""
    ddb, table = target.client("dynamodb"), target.outputs["RecordsTable"]
    body = json.dumps(value, sort_keys=True)
    ddb.put_item(TableName=table, Item=to_item({"document_id": value["document_id"], "version": value["version"],
                                                "record": body}))
    ddb.put_item(TableName=table,
                 Item=to_item({"document_id": f"HISTORY#{value['document_id']}#v{value['version']}",
                               "version": value["version"], "record": body}))
    return value


def change(target, document_id, bump=True, **patch):
    """Apply an authoritative change. Returns (before, after); `bump=False` changes status without a new version."""
    before = record(target, document_id)
    if before is None:
        raise RuntimeError(f"{document_id} is not in the authoritative records")
    after = dict(before, **patch)
    if bump:
        after["version"] = int(before["version"]) + 1
    return before, put_record(target, after)


def delete_record(target, document_id):
    """Authority no longer holds the document at all — the hardest deletion case (ADR-006)."""
    before = record(target, document_id)
    target.client("dynamodb").delete_item(TableName=target.outputs["RecordsTable"],
                                          Key={"document_id": {"S": document_id}})
    return before


def restore(target, before):
    """Put a record back after an experiment, with a new version so the change path treats it as a real change."""
    return put_record(target, dict(before, version=int(before["version"]) + 2))


# ── derived state (read-only observation) ───────────────────────────────────────────────────────────────────────────
def scan(target, prefix):
    ddb, items, kwargs = target.client("dynamodb"), [], {"TableName": target.outputs["ConvergenceTable"],
                                                         "ConsistentRead": True}
    while True:
        page = ddb.scan(**kwargs)
        items += [i for i in (from_item(raw) for raw in page.get("Items", []))
                  if str(i.get("pk", "")).startswith(prefix)]
        if "LastEvaluatedKey" not in page:
            return items
        kwargs["ExclusiveStartKey"] = page["LastEvaluatedKey"]


def convergence_state(target):
    """Everything the derived system currently knows, grouped by kind — the evidence behind a freshness claim."""
    return {name: scan(target, prefix) for name, prefix in PREFIXES.items()}


def pending(target):
    return {i["document_id"]: i for i in scan(target, CS.PENDING)}


def watermarks(target):
    return {i["change_class"]: i for i in scan(target, CS.WATERMARK)}


def reflected(target):
    return {i["document_id"]: i for i in scan(target, CS.REFLECTED)}


def generations(target, document_id=None):
    return [i for i in scan(target, CS.GENERATION) if document_id is None or i["document_id"] == document_id]


def deletions(target):
    return {i["document_id"]: i for i in scan(target, CS.DELETION)}


def reconciliations(target):
    return sorted((i for i in scan(target, CS.RECONCILIATION) if i.get("pk") != f"{CS.RECONCILIATION}LAST"),
                  key=lambda i: i.get("started_at") or "")


def last_reconciliation(target):
    runs = reconciliations(target)
    return runs[-1] if runs else None


def forget_last_reconciliation(target):
    """Remove the record of the last completed pass, so the system cannot claim completeness (VT-8, AB-1).

    This takes away the EVIDENCE, not the code: nothing about the change path is modified, and the deployment is
    restored by running reconciliation again. It is how an overdue cadence is demonstrated without waiting an hour.
    """
    item = target.client("dynamodb").get_item(TableName=target.outputs["ConvergenceTable"], ConsistentRead=True,
                                              Key={"pk": {"S": f"{CS.RECONCILIATION}LAST"}}).get("Item")
    target.client("dynamodb").delete_item(TableName=target.outputs["ConvergenceTable"],
                                          Key={"pk": {"S": f"{CS.RECONCILIATION}LAST"}})
    return from_item(item) if item else None


# ── the change path (invoked the way an operator or a schedule would) ───────────────────────────────────────────────
# Retrying an invocation is safe ONLY when the request was declined — never when it may have run. The service model is
# the evidence, not the message text. `TooManyRequestsException` is httpStatusCode 429 with `"senderFault": true`,
# documented as "The request throughput limit was exceeded", and carries `retryAfterSeconds`: the request was refused
# at the front door, so re-sending it cannot duplicate an execution. Every other candidate fails that test and is
# excluded — `ServiceException` is a 500 with `"fault": true` and may have executed; `EC2ThrottledException`,
# `ResourceNotReadyException` and `ENINotReadyException` are 502s whose execution disposition cannot be established
# from the response; so is the mount-timeout/408 family. An error whose disposition is unknown is re-raised unchanged.
RETRYABLE_INVOKE_CODES = frozenset({"TooManyRequestsException"})
INVOKE_MAX_ATTEMPTS = 6
INVOKE_RETRY_DEADLINE_SECONDS = 60
INVOKE_BACKOFF_BASE_SECONDS = 0.5
INVOKE_BACKOFF_CAP_SECONDS = 8.0

INVOKE_DIAGNOSTICS = []          # every retry decision, in order; callers copy it into their own evidence


def _error_code(error):
    """The DECLARED `Error.Code`, read explicitly. Never a substring match on the message."""
    response = getattr(error, "response", None)
    if not isinstance(response, dict):
        return None
    return (response.get("Error") or {}).get("Code")


def _retry_after_seconds(error):
    """What the service itself asked us to wait, from the Retry-After header or `retryAfterSeconds`."""
    response = getattr(error, "response", None)
    if not isinstance(response, dict):
        return None
    headers = (response.get("ResponseMetadata") or {}).get("HTTPHeaders") or {}
    for value in (headers.get("retry-after"), response.get("retryAfterSeconds")):
        try:
            seconds = float(value)
        except (TypeError, ValueError):
            continue
        if seconds >= 0:
            return seconds
    return None


def _throttle_delay(attempt, error, remaining):
    """How long to wait before the next attempt, or None when waiting would leave the deadline."""
    advertised = _retry_after_seconds(error)
    if advertised is not None:
        # Retrying sooner than the service asked is not honouring Retry-After; waiting past the deadline is not bounded.
        return advertised if advertised <= remaining else None
    backoff = min(INVOKE_BACKOFF_BASE_SECONDS * (2 ** (attempt - 1)), INVOKE_BACKOFF_CAP_SECONDS)
    delay = backoff * (0.5 + random.random() / 2)          # jittered, but never collapsing to an immediate retry
    return delay if delay <= remaining else None


def invoke(target, output_key, payload, timeout=600, diagnostics=None):
    """Invoke synchronously, retrying ONLY a request the service declined.

    `max_attempts: 0` stays on the client deliberately. botocore's own policy would also retry errors whose execution
    disposition cannot be established, silently turning one invocation into two; the decision belongs here, where it
    is explicit, bounded and recorded. Bounded means both: a maximum number of attempts AND a wall-clock deadline, so
    a sustained throttle ends in a failure rather than an unbounded wait.

    A throttled attempt is a request that did NOT execute. The diagnostics keep that distinct from an invocation, so
    nothing downstream can read "a request was attempted" as "the function ran".
    """
    client = target.client("lambda", read_timeout=timeout + 20, retries={"max_attempts": 0})
    body = json.dumps(payload).encode()          # built ONCE: the payload is never modified between attempts
    record = INVOKE_DIAGNOSTICS if diagnostics is None else diagnostics
    deadline = time.monotonic() + INVOKE_RETRY_DEADLINE_SECONDS
    for attempt in range(1, INVOKE_MAX_ATTEMPTS + 1):
        try:
            response = client.invoke(FunctionName=target.outputs[output_key],
                                     InvocationType="RequestResponse", Payload=body)
        except Exception as error:
            code = _error_code(error)
            if code not in RETRYABLE_INVOKE_CODES:
                record.append({"function": output_key, "attempt": attempt, "at": rs.now_iso(), "code": code,
                               "error": type(error).__name__, "disposition": "NON-RETRYABLE → FAILED"})
                raise
            remaining = deadline - time.monotonic()
            delay = _throttle_delay(attempt, error, remaining) if attempt < INVOKE_MAX_ATTEMPTS else None
            if delay is None:
                record.append({"function": output_key, "attempt": attempt, "at": rs.now_iso(), "code": code,
                               "seconds_remaining": round(max(remaining, 0.0), 3),
                               "disposition": "THROTTLED → RETRY EXHAUSTED"})
                raise RuntimeError(
                    f"{output_key} was declined, not invoked: {attempt} attempt(s) throttled with {code} within "
                    f"{INVOKE_RETRY_DEADLINE_SECONDS}s / {INVOKE_MAX_ATTEMPTS} attempts. No invocation of this "
                    "request executed.") from error
            record.append({"function": output_key, "attempt": attempt, "at": rs.now_iso(), "code": code,
                           "sleep_seconds": round(delay, 3), "disposition": "THROTTLED → RETRYING"})
            time.sleep(delay)
            continue
        result = json.loads(response["Payload"].read())
        if response.get("FunctionError"):
            raise RuntimeError(f"{output_key} failed: {result.get('errorType')}: "
                               f"{str(result.get('errorMessage'))[:300]}")
        return result
    raise AssertionError("unreachable: the retry loop either returns or raises on every path")


def apply_now(target, document_ids):
    """Converge these documents synchronously (the notifier normally does this asynchronously)."""
    return invoke(target, "ApplierFunctionName", {"document_ids": sorted(document_ids)})


def reconcile(target, run_id=None, change_classes=None):
    """One reconciliation pass. Repairs are applied asynchronously, so callers wait for convergence afterwards."""
    event = {k: v for k, v in (("run_id", run_id), ("change_classes", change_classes)) if v}
    return invoke(target, "ReconcilerFunctionName", event)


def rebuild(target, document_ids=None, partition=None):
    event = {k: v for k, v in (("document_ids", document_ids), ("partition", partition)) if v}
    return invoke(target, "RebuildFunctionName", event, timeout=900)


def notifier_invocations(target, since, until):
    """What the notifier actually did in this window, read from its own logs.

    Raises rather than returning nothing if the logs cannot be read: an empty list and an unreadable log group must
    never look alike to a caller deciding whether a fault was injected.
    """
    logs, group = target.client("logs"), f"/aws/lambda/{target.stack_name}-notifier"
    found, token = [], None
    while True:
        arguments = {"logGroupName": group, "startTime": int(since.timestamp() * 1000),
                     "endTime": int(until.timestamp() * 1000) + 1000}
        if token:
            arguments["nextToken"] = token
        page = logs.filter_log_events(**arguments)
        for entry in page.get("events", []):
            message = (entry.get("message") or "").strip()
            if message.startswith(("START", "END", "REPORT", "INIT")):
                continue
            found.append({"at_ms": entry.get("timestamp"), "message": message[:200]})
        token = page.get("nextToken")
        if not token:
            return found


def mapping_toggles(target, since, until):
    """Event-source-mapping changes recorded by CloudTrail — DIAGNOSTICS ONLY, never a verdict.

    Note the recorded event name carries the API version (`UpdateEventSourceMapping20150331`); querying the bare name
    returns nothing and once led this engagement to report CloudTrail as unusable when it was the query that was wrong.
    """
    try:
        events = target.client("cloudtrail").lookup_events(
            LookupAttributes=[{"AttributeKey": "EventSource", "AttributeValue": "lambda.amazonaws.com"}],
            StartTime=since, EndTime=until, MaxResults=50).get("Events", [])
    except Exception as error:                            # noqa: BLE001 — diagnostics never decide the outcome
        return {"available": False, "error": type(error).__name__}
    toggles = []
    for event in events:
        if not str(event.get("EventName") or "").startswith("UpdateEventSourceMapping"):
            continue
        detail = json.loads(event["CloudTrailEvent"])
        toggles.append({"at": event["EventTime"].isoformat(),
                        "enabled_requested": (detail.get("requestParameters") or {}).get("enabled"),
                        "state": (detail.get("responseElements") or {}).get("state")})
    return {"available": True, "toggles": sorted(toggles, key=lambda t: t["at"])}


def observed_mapping_state(target):
    """The mapping's state as it IS — read, never set. Supporting evidence only, never proof of non-delivery."""
    return target.client("lambda").get_event_source_mapping(UUID=target.outputs["RecordsStreamMappingId"])["State"]


# `prove_notifications_disabled()` was removed, not merely deprecated.
#
# It disabled the production deployment's event source mapping at runtime and then claimed the fault was injected.
# Observation established that this cannot be made deterministic: real stream records were observed delivered AFTER the
# mapping reported `Disabled` — twice in one run, with the re-enable not requested until later still — and the
# original canary could never have detected it, because a byte-identical PutItem emits no stream record at all.
# `State == "Disabled"` is supporting evidence; it is not proof of non-delivery, and no test may treat it as such.
#
# What replaces it, by case:
#   * a deployment intentionally CREATED without delivery  → `prove_no_delivery()`, which OBSERVES rather than causes
#     the condition and refuses to return a verdict when the evidence is incomplete;
#   * a test needing an interval where an authoritative change exists but convergence is incomplete → observe the
#     architecture's own pending signal under ordinary delivery, holding it open by blocking the BUILD (the build-blocking
#     pattern);
#   * an OPERATOR who genuinely needs to toggle delivery → `notifications()` via `cmd_notifications`, which is a
#     control, not evidence. Operator toggling and evidentiary proof are different concerns and stay separate.
#
# The mapping's behaviour is still unexplained.


def prove_no_delivery(target, canary="D-09", window=45, interval=2, mapping_state=None):
    """PROVE nothing is delivered — with a canary that is capable of failing. Changes no configuration.

    The previous canary wrote the record back UNCHANGED. AWS documents that a `PutItem` or `UpdateItem` which changes
    no data produces NO DynamoDB Streams record at all, so that canary could never emit the event whose absence it
    treated as proof: `delivery_disabled` collapsed to `state == "Disabled"`, and Run A delivered a real change 49
    seconds after the disable while this function reported success. A precondition that cannot distinguish success
    from non-observation is not evidence.

    So the canary is now a REAL authoritative change — a version bump on a quarantined document, which has no derived
    copies to converge and whose `new_version` class has a 4-hour window, so it cannot tip the deployment into
    conservative mode. Delivery is then looked for in two independent places: the pending set, sampled continuously
    because the applier clears entries within seconds, and the notifier's own invocations.

    Three outcomes, and only one lets an experiment proceed:

        delivery observed             → raise; the fault was not injected
        evidence incomplete           → raise; "we did not see it" is not "it did not happen"
        no delivery, evidence intact  → return the proof

    Mapping state and CloudTrail toggles are recorded because they are useful diagnostics, never because they prove
    anything: `State == "Disabled"` is supporting evidence only.
    """
    state = mapping_state or observed_mapping_state(target)
    original = record(target, canary)
    if original is None:
        raise RuntimeError(f"the delivery canary {canary} is not in the authoritative records")

    started = datetime.now(timezone.utc)
    before = set(pending(target))
    _, mutated = change(target, canary)      # a REAL change: the item's data differs, so a stream record must exist
    appearances, deadline = [], time.monotonic() + window
    while time.monotonic() < deadline:
        # Sampled continuously, not once at the end: the applier clears a pending entry within seconds, so a single
        # late snapshot cannot distinguish "never delivered" from "delivered, applied and cleared".
        seen = sorted(set(pending(target)) - before)
        if seen:
            appearances.append({"at": rs.now_iso(), "documents": seen})
        time.sleep(interval)
    ended = datetime.now(timezone.utc)

    invocations, evidence_error = [], None
    try:
        invocations = notifier_invocations(target, started, ended)
    except Exception as error:                            # noqa: BLE001 — unreadable evidence is its own outcome
        evidence_error = f"{type(error).__name__}: {' '.join(str(error).split())[:150]}"

    restored = restore(target, original)
    after_restore = record(target, canary)
    restoration_verified = (after_restore is not None
                            and after_restore.get("status") == original.get("status")
                            and int(after_restore.get("version") or 0) > int(original["version"]))

    seen_pending = sorted({d for entry in appearances for d in entry["documents"]})
    seen_notifier = [i for i in invocations if canary in i["message"]]
    delivered = bool(seen_pending or seen_notifier)
    proof = {
        "canary": canary, "mapping_state": state, "window_seconds": window, "sample_interval_seconds": interval,
        "canary_change": {"from_version": original["version"], "to_version": mutated["version"],
                          "why_it_emits_a_stream_record": "the item's data changed; DynamoDB Streams writes no record "
                                                          "for a PutItem that changes nothing, which is why the "
                                                          "previous unchanged-write canary could never fail"},
        "pending_appearances": appearances, "documents_seen_pending": seen_pending,
        "notifier_invocations": len(invocations), "notifier_mentions_canary": seen_notifier,
        "evidence_complete": evidence_error is None, "evidence_error": evidence_error,
        "mapping_toggles": mapping_toggles(target, started, ended),
        "restored_to_version": (restored or {}).get("version"), "restoration_verified": restoration_verified,
        "delivery_observed": delivered,
        "delivery_disabled": (not delivered) and evidence_error is None,
        "note": "mapping State is supporting evidence only — it is never proof that nothing was delivered",
    }
    if not restoration_verified:
        raise RuntimeError(f"the delivery canary {canary} was not restored, so the environment is not safe to "
                           f"continue from: {proof}")
    if delivered:
        raise RuntimeError(f"notification delivery is NOT disabled, so the experiment would prove nothing: {proof}")
    if evidence_error is not None:
        raise RuntimeError(f"INVALID SETUP: whether the canary was delivered could not be established "
                           f"({evidence_error}). 'Not observed' is not 'did not happen': {proof}")
    return proof


def notifications(target, enabled):
    """FX-3's switch: drop the change notifications while leaving everything else running and healthy-looking.

    The update is asynchronous, so the first read still reports the OLD state. This must therefore keep waiting for
    the state it asked for and raise if it never arrives — an earlier version returned whatever state it happened to
    read, and a caller that believed notifications were off while they were still live would turn the whole
    experiment into theatre.
    """
    lam = target.client("lambda")
    mapping = target.outputs["RecordsStreamMappingId"]
    lam.update_event_source_mapping(UUID=mapping, Enabled=bool(enabled))
    wanted = "Enabled" if enabled else "Disabled"
    deadline = time.monotonic() + 180
    state = None
    while time.monotonic() < deadline:
        state = lam.get_event_source_mapping(UUID=mapping)["State"]
        if state == wanted:
            return state
        time.sleep(3)
    raise RuntimeError(f"event source mapping did not reach {wanted} (last state {state})")


# ── waiting, without ever waiting for something the architecture forbids ────────────────────────────────────────────
def wait_for_pending(target, document_id, timeout=180, interval=5):
    """Wait for a pending entry to APPEAR for this document, and return it (or None).

    Absence of a pending entry does not mean "converged" — it far more often means "not delivered yet". Delivery has
    been measured at up to 42 seconds, so a test that reads the pending set immediately sees an empty one and would
    conclude the change had already been applied.
    """
    deadline = time.monotonic() + timeout
    while True:
        entry = pending(target).get(document_id)
        if entry is not None or time.monotonic() > deadline:
            return entry
        time.sleep(interval)


def wait_until_applied(target, document_ids, timeout=300, interval=5):
    """Wait until no pending entry remains for these documents. Returns (converged, what is still pending)."""
    document_ids, deadline = set(document_ids), time.monotonic() + timeout
    while True:
        open_items = {d: p for d, p in pending(target).items() if d in document_ids}
        if not open_items or time.monotonic() > deadline:
            return not open_items, open_items
        time.sleep(interval)


def wait_for_watermark_after(target, moment, timeout=300, interval=5):
    """Wait until every class watermark is proven through at least `moment` (a completed pass, never a notification)."""
    from core import convergence as cv
    deadline = time.monotonic() + timeout
    while True:
        marks = watermarks(target)
        proven = {c: (marks.get(c) or {}).get("proven_through") for c in cv.CHANGE_CLASSES}
        if all(p is not None and p >= moment for p in proven.values()) or time.monotonic() > deadline:
            return proven
        time.sleep(interval)


def converge(target, document_ids=None, run_id=None):
    """The ordinary operator sequence: reconcile, let the repairs run, and report what the system can then claim."""
    started = rs.now_iso()
    summary = reconcile(target, run_id=run_id)
    requested = summary.get("repairs_requested") or []
    if requested:
        wait_until_applied(target, requested)
    return {"reconciliation": summary, "watermarks_after": wait_for_watermark_after(target, started),
            "pending_after": sorted(pending(target)),
            "documents": sorted(document_ids) if document_ids else None}
