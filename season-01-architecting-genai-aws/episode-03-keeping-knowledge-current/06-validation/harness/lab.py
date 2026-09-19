"""The learner lab: one command per architectural action, with output written to be read on screen.

Two deployments, never one (the approved lab design):

    Part A · delivery-off   change notifications are OFF FROM CREATION, so a stale copy can survive a change and the
                            learner can watch the request refuse it and reconciliation repair it.
    Part B · delivery-on    live delivery, so a real change enters the normal path, fails to apply, stays pending, is
                            retried, escalates, and recovers.

Every value printed here is READ from the running deployment — the records system, the convergence store, the index,
the audit record of the request, CloudWatch. Nothing is inferred from the command that was just run, and no outcome
is ever written into the output as a constant: if the system does something unexpected, the learner sees that.

It writes no files, and it never switches change notifications on or off at runtime: that switch was shown to be
unreliable, which is why Part A is created without notifications instead.
"""
import json
import textwrap
import time
from datetime import datetime, timezone

from harness import canaries, currency, fixtures
from harness.common import redact, tla_ops
from harness.context import Context
from harness.identities import Identities
from harness.target import Target

from core import freshness, record_state as rs

PARTS = dict(tla_ops.LAB_PARTS)                 # part → variant
PART_TITLE = {"delivery-off": "Part A (delivery off)", "delivery-on": "Part B (delivery on)"}
RECLASSIFY_UP_TO = {"D-04": {"document_label": "CONFIDENTIAL", "document_scope": "SI-0417"}}
WIDTH = 100


class LabError(Exception):
    """A learner-facing refusal: printed as one clear sentence, never as a traceback."""


# ── which lab part is running ───────────────────────────────────────────────────────────────────────────────────────
def running_parts(existing):
    """Lab parts whose stack exists, from `tla_ops.existing_stacks()` output (variant → status)."""
    return sorted(part for part, variant in PARTS.items() if variant in existing)


def choose_part(running, required=None):
    """The one running part a command should act on — or a refusal that says exactly what to do instead."""
    if not running:
        raise LabError("No lab deployment is running. Start one: python3 scripts/tla_ops.py lab-up delivery-off "
                       "(Part A) or lab-up delivery-on (Part B), from 05-implementation/.")
    if len(running) > 1:
        raise LabError(f"Both lab parts are running ({', '.join(running)}). End one with lab-down.")
    part = running[0]
    if required and part != required:
        raise LabError(REQUIRED_PART_REASON[required] + f" The running deployment is {PART_TITLE[part]}.")
    return part


REQUIRED_PART_REASON = {
    "delivery-off": "This step belongs to Part A. It needs a deployment created WITHOUT change notifications — with "
                    "delivery on, the notification would remove the stale copy within seconds and there would be "
                    "nothing to observe.",
    "delivery-on": "This step belongs to Part B. It needs LIVE change notifications — only the notifier classifies "
                   "an upward reclassification, whose window is zero seconds.",
}


def lab_target(required=None):
    config = tla_ops.load_config()
    session = tla_ops.session(config)
    tla_ops.account_guard(config, session, quiet=True)
    part = choose_part(running_parts(lab_stacks(session.client("cloudformation"))), required)
    return part, Target(PARTS[part])


def lab_stacks(cfn):
    """Only the two lab stacks are looked up — every learner command starts here, so it has to be quick."""
    found = {}
    for variant in PARTS.values():
        try:
            found[variant] = cfn.describe_stacks(StackName=tla_ops.VARIANTS[variant][0])["Stacks"][0]["StackStatus"]
        except Exception:  # noqa: BLE001 — an absent stack is the ordinary case
            pass
    return found


# ── output helpers ──────────────────────────────────────────────────────────────────────────────────────────────────
def block(title, rows):
    """A titled block of `label  value` rows. Values are shown exactly as read."""
    lines = [title]
    width = max((len(label) for label, _ in rows), default=0)
    for label, value in rows:
        lines.append(f"  {label.ljust(width)}  {value}")
    return lines


def wrap(text, indent="  "):
    return textwrap.fill(str(text), WIDTH, initial_indent=indent, subsequent_indent=indent)


def emit(lines):
    for line in lines:
        print(line)


def section(document_id, section_id, version=None, label=None, scope=None):
    tail = f" v{version}" if version is not None else ""
    if label is not None or scope is not None:
        tail += f"  ({label or 'no label'} / {scope or 'no scope'})"
    return f"{document_id}-{section_id}{tail}"


def age_seconds(moment, now):
    if not moment:
        return None
    then = datetime.fromisoformat(str(moment).replace("Z", "+00:00"))
    return int((now - then).total_seconds())


def human_age(seconds):
    if seconds is None:
        return "unknown"
    minutes, secs = divmod(max(seconds, 0), 60)
    return f"{minutes} min {secs:02d} s" if minutes else f"{secs} s"


# ── views: pure functions of observed state ─────────────────────────────────────────────────────────────────────────
def ask_view(question_text, persona, audit, body):
    """What happened to one request, from its own audit record. A missing audit is reported, never filled in."""
    if not audit:
        return ["Request", "  outcome   UNKNOWN — the request left no audit record (see Troubleshooting)"]
    body = body if isinstance(body, dict) else {}
    retrieval = audit.get("retrieval") or []
    verification = audit.get("verification") or {}
    states = (audit.get("convergence") or {}).get("document_states") or {}
    by_chunk = {e.get("chunk_id"): e for e in retrieval}
    lines = [f"Question  {question_text}", f"Asked as  {persona}", ""]
    if retrieval:
        lines.append("Retrieved from the index")
        for entry in sorted(retrieval, key=lambda e: (e.get("document_id") or "", e.get("section_id") or "")):
            lines.append("  " + section(entry.get("document_id"), entry.get("section_id"), entry.get("record_version"),
                                        entry.get("label"), entry.get("scope")))
    else:
        lines.append("Retrieved from the index")
        lines.append("  nothing")
    retrieved_documents = sorted({e.get("document_id") for e in retrieval if e.get("document_id")})
    if retrieved_documents:
        lines += ["", "Checked against the records system on this request"]
        for document_id in retrieved_documents:
            lines.append(f"  {document_id}  {states.get(document_id, 'not checked')}")
    mismatches = verification.get("mismatches") or []
    if mismatches:
        lines += ["", "Refused copies"]
        for mismatch in sorted(mismatches, key=lambda m: (by_chunk.get(m.get("chunk_id")) or {}).get("section_id") or ""):
            entry = by_chunk.get(mismatch.get("chunk_id")) or {}
            name = section(entry.get("document_id"), entry.get("section_id"), entry.get("record_version")) \
                if entry else str(mismatch.get("chunk_id"))[:8]
            lines.append(f"  {name}  {mismatch.get('reason')}")
    control = audit.get("failing_control")
    generation = (audit.get("generation") or {}).get("invoked")
    lines += ["", "Request",
              f"  outcome        {audit.get('outcome')}" + (f"   (stopped at {control})" if control else ""),
              f"  model invoked  {'yes' if generation else 'no'}"]
    citations = body.get("citations") or []
    lines.append("  cited          " + (", ".join(section(c.get("document_id"), c.get("section_id"),
                                                          c.get("record_version")) for c in citations) or "nothing"))
    if mismatches:
        refused = sorted({section((by_chunk.get(m.get("chunk_id")) or {}).get("document_id"),
                                  (by_chunk.get(m.get("chunk_id")) or {}).get("section_id"))
                          for m in mismatches if by_chunk.get(m.get("chunk_id"))})
        lines += ["", f"=> COPY: PRESENT (retrieved {', '.join(refused) or len(mismatches)})   "
                      f"REQUEST: {audit.get('outcome')}"]
    if body.get("answer"):
        lines += ["", "Answer"] + wrap(body["answer"]).splitlines()
    return lines


def inspect_view(document_id, record, reflected, copies, pending_entry, delivery):
    """Authority beside what the index holds, so presence and currency can be compared directly."""
    lines = block("Authority (records system)", [
        ("status", record.get("status") if record else "NOT HELD (the record was deleted)"),
        ("version", record.get("version") if record else "—"),
        ("label / scope", f"{record.get('document_label')} / {record.get('document_scope') or 'none'}" if record else "—"),
    ])
    chunks = copies.get("chunks") or []
    lines += [""] + block("Index (derived state)", [
        ("believes", f"{reflected.get('status')} v{reflected.get('version')}" if reflected else "nothing recorded"),
        ("copies", "PRESENT" if chunks else "ABSENT"),
    ])
    for chunk in chunks:
        lines.append("    " + section(chunk["document_id"], chunk["section_id"], chunk.get("record_version"),
                                      chunk.get("label"), chunk.get("scope")))
    lines += ["", "Change path",
              f"  pending        {describe_pending(pending_entry)}",
              f"  notifications  {delivery}"]
    lines += [""] + [row for part in verdict_line(record, reflected, chunks, pending_entry).split("\n")
                     for row in wrap(part, indent="").splitlines()]
    return lines


def describe_pending(entry):
    if not entry:
        return "none"
    return f"YES — {entry.get('change_class')}, attempts {entry.get('attempts')}"


def verdict_line(record, reflected, chunks, pending_entry):
    authority = (record or {}).get("status") or "NOT HELD"
    believed = (reflected or {}).get("status")
    if pending_entry:
        return f"=> A change is KNOWN and not yet applied: the request path treats {record.get('document_id') if record else 'it'} as pending."
    if chunks and authority != "IN_FORCE":
        return (f"=> DIVERGED: authority says {authority}; the index still believes {believed}.\n"
                "=> The copy exists. It must not be trusted.")
    if chunks and believed == authority and int((reflected or {}).get("version") or -1) == int((record or {}).get("version") or -2):
        return "=> In agreement: authority and index describe the same version."
    if not chunks and authority != "IN_FORCE":
        return f"=> Converged: authority says {authority} and nothing remains in the index to retrieve."
    return f"=> Authority {authority}; index believes {believed}; copies {'present' if chunks else 'absent'}."


def repair_outcomes(requested, before, after):
    """Per requested document: REPAIRED (no longer pending), RETRY FAILED (attempts rose, still pending) or WAITING.

    The reconciler writes a pending entry for every repair BEFORE it invokes the applier, so absence after the pass
    means the applier finished the work — it cannot mean "not started yet".
    """
    outcomes = {}
    for document_id in requested:
        now = after.get(document_id)
        if now is None:
            outcomes[document_id] = "REPAIRED"
            continue
        was = before.get(document_id)
        if was is not None and int(now.get("attempts") or 0) > int(was.get("attempts") or 0):
            outcomes[document_id] = "RETRY FAILED"
        elif was is None and int(now.get("attempts") or 0) > 0:
            outcomes[document_id] = "RETRY FAILED"
        else:
            outcomes[document_id] = "WAITING"
    return outcomes


def describe_difference(entry):
    """One reconciliation difference in words, from whichever fields the reconciler reported for it.

    A status divergence carries statuses; a version divergence, a missing document and an extra copy carry versions.
    Each is described from its own fields — a field the reconciler did not report is never printed as a value.
    """
    if not isinstance(entry, dict):
        return str(entry)
    document_id = entry.get("document_id")
    if "authoritative_status" in entry:
        return f"{document_id} (authority {entry['authoritative_status']}, index {entry.get('reflected_status')})"
    if "authoritative_version" in entry and entry.get("reflected_version") is not None:
        return f"{document_id} (authority v{entry['authoritative_version']}, index v{entry['reflected_version']})"
    if "authoritative_version" in entry:
        return f"{document_id} (authority v{entry['authoritative_version']}, index holds nothing)"
    if "reflected_version" in entry:
        return f"{document_id} (authority holds nothing, index v{entry['reflected_version']})"
    return str(document_id)


def describe_failure(failure):
    error, code = failure.get("error"), failure.get("code")
    reason = error if not code or code == error else f"{error} {code}"
    return f"{reason} on {failure.get('operation') or 'apply'}"


def reconcile_view(summary, outcomes, pending_after, confirmation=None):
    lines = [f"Reconciliation compared {summary.get('documents_compared')} documents in the records system with "
             "the index.", ""]
    rows = [(kind, ", ".join(describe_difference(d) for d in summary.get(kind) or []) or "none")
            for kind in ("missing", "extra", "divergent")]
    lines += block("Differences found", [("diverged" if k == "divergent" else k, v) for k, v in rows])
    if outcomes:
        lines += [""] + block("Repairs", [(d, o) for d, o in sorted(outcomes.items())])
    escalation = summary.get("escalation") or {}
    breaches = escalation.get("breaches") or {}
    lines += ["", "Freshness windows"]
    newly = set(escalation.get("newly_escalated") or [])
    if breaches:
        for change_class, documents in sorted(breaches.items()):
            for document_id in documents:
                how = ("ESCALATED on this pass — alert raised" if document_id in newly
                       else "already escalated; not raised again")
                lines.append(f"  BREACHED  {change_class} (window {freshness.WINDOW_SECONDS.get(change_class)} s): "
                             f"{document_id} — {how}")
    else:
        lines.append("  no change has outlived its window")
    lines.append(f"  still pending  {', '.join(sorted(pending_after)) or 'nothing'}")
    if confirmation is not None:
        clean = not (confirmation.get("missing") or confirmation.get("extra") or confirmation.get("divergent")
                     or confirmation.get("repairs_requested"))
        lines += ["", f"Confirmation pass: compared {confirmation.get('documents_compared')}, "
                      + ("nothing left to repair — CONVERGED" if clean else
                         f"still found {confirmation.get('repairs_requested')}")]
    return lines


def incident_view(document_id, entry, now, failure, alarm, record=None, reflected=None):
    """The operator's view of one change: is it still pending, how old, retried, escalated — and the alarm."""
    if not entry:
        lines = [f"No open incident for {document_id}."]
        if record and reflected:
            lines.append(f"  authority v{record.get('version')} {record.get('document_label')} · index "
                         f"{reflected.get('status')} v{reflected.get('version')}")
    else:
        change_class = entry.get("change_class")
        window = freshness.WINDOW_SECONDS.get(change_class)
        age = age_seconds(entry.get("noticed_at"), now)
        lines = block(f"Incident: {document_id} — change still PENDING", [
            ("change class", change_class),
            ("noticed at", f"{entry.get('noticed_at')}   (age {human_age(age)})"),
            ("window", f"{window} s — " + ("BREACHED" if age is not None and window is not None and age > window
                                             else "inside the window")),
            ("attempts", f"{entry.get('attempts')}   (last {entry.get('last_attempt_at') or 'never'})"),
            ("escalated", entry.get("escalated_at") or "not yet — escalation happens on a reconciliation pass"),
        ])
        if failure:
            lines.append(f"  last failure  {describe_failure(failure)} (attempted v{failure.get('attempted_version')}, "
                         f"serving v{failure.get('serving_version')})")
    if alarm:
        lines += ["", f"Alarm {alarm.get('name')}: {alarm.get('state')} (since {alarm.get('since')})"]
        if alarm.get("state") == "ALARM" and not entry:
            lines.extend(wrap("The breach is repaired. The alarm takes the maximum over a one-hour period, so it "
                              "stays in ALARM until that period rolls over, then returns to OK by itself — it does "
                              "not latch.").splitlines())
    return lines


# ── state readers (operator credentials; read-only) ─────────────────────────────────────────────────────────────────
def derived_copies(target, document_id):
    inventory = Context(target, None).obs.inventory()
    return {"chunks": sorted((c for tier in inventory.values() for c in tier["chunks"]
                              if c["document_id"] == document_id),
                             key=lambda c: (c["section_id"] or "")),
            "section_objects": sorted(k for tier in inventory.values() for k in tier["section_objects"]
                                      if k.startswith(f"sections/{document_id}/"))}


def delivery_state(target):
    created = target.change_notifications_enabled
    mapping = currency.observed_mapping_state(target)
    if created == "false":
        return f"OFF since creation (stream mapping {mapping})"
    return f"ON (stream mapping {mapping})"


def alarm_state(target):
    name = target.outputs.get("WindowBreachAlarmName")
    alarms = target.client("cloudwatch").describe_alarms(AlarmNames=[name]).get("MetricAlarms") or []
    if not alarms:
        return {"name": name, "state": "NOT FOUND", "since": "—"}
    alarm = alarms[0]
    since = alarm.get("StateUpdatedTimestamp")
    return {"name": name, "state": alarm.get("StateValue"),
            "since": since.astimezone(timezone.utc).isoformat(timespec="seconds") if since else "—"}


def latest_failure(target, document_id, since):
    for report in reversed(Context(target, None).obs.change_reports()):
        if (report.get("timestamp") or "") < (since or ""):
            continue
        for failure in report.get("failed", []):
            if failure.get("document_id") == document_id:
                return failure
    return None


def source_present(s3, bucket, key):
    """Whether the source object exists, by exact-key LISTING.

    Never by HeadObject/GetObject: the records bucket lets only the change function read objects, so any other reader
    gets 403 whether or not the object exists — and a 403 must never be read as "removed" (rehearsal finding).
    """
    listed = s3.list_objects_v2(Bucket=bucket, Prefix=key).get("Contents") or []
    return any(item.get("Key") == key for item in listed)


def _require_document(target, document_id):
    record = currency.record(target, document_id)
    if record is None:
        raise LabError(f"{document_id} is not in the records system. The lab corpus holds D-01 … D-15.")
    return record


# ── commands ────────────────────────────────────────────────────────────────────────────────────────────────────────
def prepare(part):
    """Load the synthetic records system and build the index — called by lab-up once the stack exists."""
    target = Target(PARTS[part])
    if part == "delivery-off" and target.change_notifications_enabled != "false":
        raise LabError("Part A's deployment reports change notifications ON — it must be created without them. "
                       "Run lab-down delivery-off, then lab-up delivery-off again.")
    report = fixtures.load(target, Identities(target), reset=True)
    reconciliation = report.get("reconciliation") or {}
    emit(block(f"{PART_TITLE[part]} is loaded", [
        ("documents", f"{report.get('documents')} in the records system; {len(report.get('converged') or [])} "
                      f"reflected in the index"),
        ("people", f"{report.get('personas')} synthetic employees"),
        ("reconciliation", f"compared {reconciliation.get('documents_compared')} — missing "
                           f"{len(reconciliation.get('missing') or [])}, extra {len(reconciliation.get('extra') or [])}, "
                           f"diverged {len(reconciliation.get('divergent') or [])}"),
        ("pending", ", ".join(report.get("pending_after_load") or []) or "nothing"),
        ("notifications", delivery_state(target)),
    ]))
    alarm = alarm_state(target)
    if alarm.get("state") == "ALARM":
        emit(["", f"NOTE: the window-breach alarm is already in ALARM (since {alarm.get('since')}) from an earlier run on "
                  "this deployment. It returns to OK by itself after its one-hour period. For a completely fresh "
                  "start, run lab-down, then lab-up."])
    return 0 if report.get("canonical") and not report.get("pending_after_load") else 1


def cmd_ask(question, persona, verbose=False):
    _, target = lab_target()
    ctx = Context(target, None)
    text = ctx.questions[question]["text"] if question in ctx.questions else question
    observation = ctx.ask(persona, question)
    emit(ask_view(text, persona, observation.audit, observation.body))
    if verbose:
        print("\n" + json.dumps(redact(observation.view()), indent=2, default=str))
    return 0


def cmd_inspect(document_id, verbose=False):
    _, target = lab_target()
    record = currency.record(target, document_id)
    reflected = currency.reflected(target).get(document_id)
    copies = derived_copies(target, document_id)
    entry = currency.pending(target).get(document_id)
    emit([f"{document_id} — {(record or {}).get('title') or ''}", ""])
    emit(inspect_view(document_id, record, reflected, copies, entry, delivery_state(target)))
    if verbose:
        print("\n" + json.dumps(redact({"record": record, "reflected": reflected, "copies": copies, "pending": entry}),
                                indent=2, default=str))
    return 0


def cmd_withdraw(document_id):
    _, target = lab_target(required="delivery-off")
    before = _require_document(target, document_id)
    if before.get("status") != "IN_FORCE":
        raise LabError(f"{document_id} is already {before.get('status')} in the records system. Reset Part A with "
                       "lab-up delivery-off to start again.")
    # Withdrawal changes STATUS, not content, so the version stays the same: label, scope and version of the copy in
    # the index will all still match — only authority's status says it is no longer in force.
    _, after = currency.change(target, document_id, bump=False, status="WITHDRAWN", effective_from=rs.now_iso())
    after = currency.record(target, document_id)
    pending = currency.pending(target)
    emit(block(f"Authority changed: {document_id}", [
        ("status", f"{before.get('status')} -> {after.get('status')}"),
        ("version", f"v{before.get('version')} -> v{after.get('version')} (a withdrawal does not edit the document)"),
        ("effective", after.get("effective_from")),
    ]))
    emit(["", f"Notifications: {delivery_state(target)} — nothing told the index.",
          f"Changes the index knows are pending: {', '.join(sorted(pending)) or 'none'}"])
    return 0


def cmd_reconcile(verbose=False, timeout=240):
    _, target = lab_target()
    before = currency.pending(target)
    summary = currency.reconcile(target, run_id=f"lab-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}")
    requested = summary.get("repairs_requested") or []
    outcomes, after = {}, before
    if requested:
        print(f"repairs requested for {', '.join(requested)} — waiting for the change path to finish …")
        deadline = time.monotonic() + timeout
        while True:
            after = currency.pending(target)
            outcomes = repair_outcomes(requested, before, after)
            if "WAITING" not in outcomes.values() or time.monotonic() > deadline:
                break
            time.sleep(5)
    else:
        after = currency.pending(target)
    confirmation = None
    if requested and set(outcomes.values()) == {"REPAIRED"}:
        confirmation = currency.reconcile(target, run_id=f"lab-confirm-{int(time.time())}")
        after = currency.pending(target)
    emit(reconcile_view(summary, outcomes, after, confirmation))
    if verbose:
        print("\n" + json.dumps(redact({"pass": summary, "confirmation": confirmation}), indent=2, default=str))
    return 0


def cmd_obstruct(document_id):
    _, target = lab_target(required="delivery-on")
    _require_document(target, document_id)
    bucket, key = target.outputs["RecordsBucket"], f"records/{document_id}.md"
    target.client("s3").delete_object(Bucket=bucket, Key=key)
    present = source_present(target.client("s3"), bucket, key)
    emit(block(f"Obstruction: the source text of {document_id}", [
        ("source", "PRESENT (the removal did not take effect)" if present else "REMOVED from the records system"),
        ("unchanged", "the authoritative record, the code, the permissions and delivery"),
        ("effect", f"the next build of {document_id} cannot read its text"),
    ]))
    return 0 if not present else 1


def cmd_reclassify_up(document_id, timeout=200):
    _, target = lab_target(required="delivery-on")
    if document_id not in RECLASSIFY_UP_TO:
        raise LabError(f"The lab reclassifies D-04 (safety investigation SI-0417) — its case scope is defined in the "
                       f"corpus. {document_id} has no upward reclassification defined.")
    before = _require_document(target, document_id)
    patch = RECLASSIFY_UP_TO[document_id]
    if before.get("document_label") == patch["document_label"]:
        raise LabError(f"{document_id} is already {before.get('document_label')}. Reset Part B with lab-up "
                       "delivery-on to start again.")
    since = rs.now_iso()
    _, after = currency.change(target, document_id, bump=True, **patch)
    emit(block(f"Authority changed: {document_id}", [
        ("label", f"{before.get('document_label')} -> {after.get('document_label')}"),
        ("scope", f"{before.get('document_scope') or 'none'} -> {after.get('document_scope')}"),
        ("version", f"v{before.get('version')} -> v{after.get('version')}"),
    ]))
    print("\nwaiting for the change notification and the attempt to apply it (usually under a minute) …")
    deadline, entry, failure, applied = time.monotonic() + timeout, None, None, False
    while time.monotonic() < deadline:
        entry = currency.pending(target).get(document_id) or entry
        failure = latest_failure(target, document_id, since)
        reflected = currency.reflected(target).get(document_id) or {}
        applied = int(reflected.get("version") or 0) >= int(after["version"]) and not currency.pending(target).get(document_id)
        if (entry and failure) or applied:
            break
        time.sleep(5)
    current = currency.pending(target).get(document_id)
    rows = [("notification", f"received — pending entry noticed at {entry.get('noticed_at')}, class "
                             f"{entry.get('change_class')}" if entry else "not observed within the wait"),
            ("application", f"FAILED — {describe_failure(failure)}" if failure else
                            ("APPLIED — nothing obstructed it (did you run lab-obstruct first?)" if applied
                             else "no result recorded yet — run lab-incident in a moment")),
            ("pending", describe_pending(current))]
    emit([""] + block("What the change path did", rows))
    return 0


def cmd_incident(document_id, wait_for_alarm=False, timeout=300):
    _, target = lab_target(required="delivery-on")
    entry = currency.pending(target).get(document_id)
    alarm = alarm_state(target)
    if wait_for_alarm and entry and entry.get("escalated_at") and alarm.get("state") != "ALARM":
        print("escalation raised; waiting for CloudWatch to evaluate the alarm (usually 1–3 minutes) …")
        deadline = time.monotonic() + timeout
        while alarm.get("state") != "ALARM" and time.monotonic() < deadline:
            time.sleep(15)
            alarm = alarm_state(target)
    failure = latest_failure(target, document_id, (entry or {}).get("noticed_at")) if entry else None
    record = currency.record(target, document_id)
    reflected = currency.reflected(target).get(document_id)
    emit(incident_view(document_id, entry, datetime.now(timezone.utc), failure, alarm, record, reflected))
    return 0


def cmd_unobstruct(document_id):
    _, target = lab_target(required="delivery-on")
    _require_document(target, document_id)
    bucket, key = target.outputs["RecordsBucket"], f"records/{document_id}.md"
    target.client("s3").put_object(Bucket=bucket, Key=key, Body=canaries.markdown(document_id).encode(),
                                   ContentType="text/markdown; charset=utf-8")
    present = source_present(target.client("s3"), bucket, key)
    entry = currency.pending(target).get(document_id)
    emit(block(f"Obstruction removed: the source text of {document_id}", [
        ("source", "RESTORED" if present else "STILL ABSENT (the write did not take effect)"),
        ("pending", describe_pending(entry)),
    ]))
    if entry:
        emit(["", "Nothing retries a change by itself here: the next reconciliation pass will. Run lab-reconcile."])
    return 0 if present else 1


def run(command, **arguments):
    """Dispatch a learner command, turning a LabError into one readable refusal and exit code 2."""
    try:
        return command(**arguments)
    except LabError as refusal:
        print(textwrap.fill(f"REFUSED: {refusal}", WIDTH, subsequent_indent="  "))
        return 2
    except Exception as error:  # noqa: BLE001 — an AWS or network failure, reported in one line
        if not type(error).__module__.startswith(("botocore", "urllib3", "socket")):
            raise
        code = ((getattr(error, "response", None) or {}).get("Error") or {}).get("Code") or type(error).__name__
        print(f"AWS REQUEST FAILED: {code} — {' '.join(str(error).split())[:200]}")
        print("Every lab command is safe to repeat: run the same command again. If it keeps failing, see "
              "Troubleshooting in the lab README.")
        return 3


def learner_commands():
    """Name → (function, argument spec). The CLI builds its lab-* verbs from this and nothing else."""
    return {
        "lab-ask": (cmd_ask, "ask a question as one of the synthetic employees"),
        "lab-inspect": (cmd_inspect, "compare authority with what the index holds for one document"),
        "lab-withdraw": (cmd_withdraw, "Part A: withdraw a document in the records system"),
        "lab-reconcile": (cmd_reconcile, "run one reconciliation pass and show what it found and repaired"),
        "lab-obstruct": (cmd_obstruct, "Part B: remove a document's source text so its next build fails"),
        "lab-reclassify-up": (cmd_reclassify_up, "Part B: reclassify a document upwards through normal delivery"),
        "lab-incident": (cmd_incident, "Part B: show the pending change, its age, retries, escalation and alarm"),
        "lab-unobstruct": (cmd_unobstruct, "Part B: put the document's source text back"),
    }


def add_cli(sub):
    """The learner lab: one verb per architectural action. They act on whichever lab part is running."""
    commands = learner_commands()
    arguments = {
        "lab-ask": lambda p: (p.add_argument("question", help="a question id such as induction_ppe, or your own text"),
                              p.add_argument("--as", dest="persona", required=True, help="a persona such as P-01"),
                              p.add_argument("--verbose", action="store_true")),
        "lab-inspect": lambda p: (p.add_argument("document_id"), p.add_argument("--verbose", action="store_true")),
        "lab-withdraw": lambda p: p.add_argument("document_id"),
        "lab-reconcile": lambda p: p.add_argument("--verbose", action="store_true"),
        "lab-obstruct": lambda p: p.add_argument("document_id"),
        "lab-reclassify-up": lambda p: p.add_argument("document_id"),
        "lab-incident": lambda p: (p.add_argument("document_id"),
                                   p.add_argument("--wait-for-alarm", dest="wait_for_alarm", action="store_true",
                                                  help="if the change has escalated, wait for the alarm to fire")),
        "lab-unobstruct": lambda p: p.add_argument("document_id"),
    }
    for name, (function, text) in commands.items():
        p = sub.add_parser(name, help=text, description=text)
        arguments[name](p)
        p.set_defaults(func=lambda args, f=function: run(
            f, **{k: v for k, v in vars(args).items() if k not in ("func", "command")}))
