"""Fixture loader (PRIVILEGED: the sandbox operator writes the simulated authoritative systems).

  * records system:        fixtures/records/D-NN.md → records bucket
  * authoritative records: one item per document (current) + HISTORY#<document>#v<version> items for reconstruction,
                           now carrying the lifecycle fields of ADR-001 (status, effective_from, superseded_by)
  * identities:            one Cognito user per persona; token groups mirror grants ONLY where the fixture says so
  * grants store:          HR and GRANTS records keyed by the identity subject, + HR#v… / GRANTS#v… history items
                           (P-09 gets an identity and no records)
  * derived state:         built by the CHANGE PATH. Episode 02's separate ingestion job is gone: the applier is the
                           single writer of derived retrieval state (ADR-004), so the initial load is simply the first
                           change every document goes through.
  * completeness:          one reconciliation pass at the end. A deployment that has never proven completeness cannot
                           make a freshness claim, and therefore withholds (ADR-002, ADR-007) — loading fixtures
                           without reconciling would leave every later test looking at a system that answers nothing.
"""
import json
import os
import re
import time

from harness import canaries, currency
from adapters.stores import to_item
from core import record_state as rs

# The convergence rows that belong to ONE document. Watermarks and reconciliation history are deliberately absent:
# they are the deployment's record of what it has proven, shared across every document, and a fixture reload must
# never quietly rewrite them.
DERIVED_PREFIXES = ("REFLECTED", "GENERATION", "PENDING", "DELETION")


def with_lifecycle(record):
    """Episode 02's records predate the lifecycle fields; the corpus states them explicitly so the model is visible."""
    return dict(record, status=record.get("status", rs.IN_FORCE),
                effective_from=record.get("effective_from"), superseded_by=record.get("superseded_by"))


def put_classification(ddb, table, record):
    """Write an authoritative record and its version history. (The records table is Episode 02's, extended.)"""
    body = json.dumps(record, sort_keys=True)
    ddb.put_item(TableName=table, Item=to_item({"document_id": record["document_id"], "version": record["version"],
                                                "record": body}))
    ddb.put_item(TableName=table, Item=to_item({"document_id": f"HISTORY#{record['document_id']}#v{record['version']}",
                                                "version": record["version"], "record": body}))


def put_grants(ddb, table, subject, persona, domains=None, cases=None, grants_version=None, status=None,
               hr_version=None):
    hr = {"requester_sub": subject, "record": "HR", "employee_id": persona["employee_id"],
          "employment_status": status or persona["employment_status"], "hr_version": hr_version or persona["hr_version"]}
    grants = {"requester_sub": subject, "record": "GRANTS",
              "domains": list(persona["domains"] if domains is None else domains),
              "cases": list(persona["cases"] if cases is None else cases),
              "grants_version": grants_version or persona["grants_version"]}
    for item in (hr, grants):
        ddb.put_item(TableName=table, Item=to_item(item))
        history = dict(item, record=f"{item['record']}#v{item['hr_version' if item['record'] == 'HR' else 'grants_version']}")
        ddb.put_item(TableName=table, Item=to_item(history))


def apply_documents(target, document_ids):
    """Converge these documents through the change path — the same path a notification or a repair would use."""
    return currency.apply_now(target, document_ids)


# Recovery-tool operating values, chosen for THIS loader's workload. They are not an architectural benchmark and not
# a production throughput recommendation. Deleting fifteen records at once with delivery enabled produced fourteen
# notifier invocations in seven seconds, and the loader's own explicit invoke was then throttled. Pacing stops
# the loader manufacturing that burst; it says nothing about what the architecture can sustain.
LOADER_BATCH = 3
LOADER_BATCH_PAUSE_SECONDS = 3
WITHDRAW_PROPAGATION_TIMEOUT_SECONDS = 120
WITHDRAW_POLL_SECONDS = 5

PHASES = ("PREFLIGHT", "WITHDRAW_AUTHORITY", "AWAIT_WITHDRAW_PROPAGATION", "VERIFY_WITHDRAWAL",
          "REPAIR_WITHDRAWAL_STRAGGLERS", "VERIFY_WITHDRAWAL_COMPLETE", "RESET_BOOKKEEPING", "RESTORE_AUTHORITY",
          "REBUILD_DERIVED_STATE", "VERIFY_CANONICAL_STATE", "COMPLETE")


class LoaderPhases:
    """Where an interrupted load actually stopped.

    A phase is COMPLETED only when its postcondition has been established — never merely because execution entered
    it. The incident that motivated this left authority deleted and nothing rewritten, and the traceback alone could
    not say which phase had finished.
    """

    def __init__(self):
        self.completed, self.current, self.started_at = [], None, rs.now_iso()

    def enter(self, name):
        self.current = name
        return name

    def complete(self, name, detail=None):
        self.completed.append({"phase": name, "at": rs.now_iso(), "detail": detail})
        self.current = None

    def report(self, error=None):
        record = {"started_at": self.started_at, "at": rs.now_iso(), "current_phase": self.current,
                  "completed_phases": self.completed,
                  "phases_not_reached": [p for p in PHASES
                                         if p not in {c["phase"] for c in self.completed} and p != self.current]}
        if error is not None:
            response = getattr(error, "response", None)
            record["failure"] = {
                "error": type(error).__name__, "message": " ".join(str(error).split())[:200],
                "code": ((response or {}).get("Error") or {}).get("Code") if isinstance(response, dict) else None,
                "operation": getattr(error, "operation_name", None)}
        return record


GENERATION_ID = re.compile(r"^(D-\d+)-S\d+-g\d+$")


def indexed_documents(target, tier):
    """Every document identifier the tier's knowledge base still holds."""
    knowledge_base_id, data_source_id = target.knowledge_base(tier)
    agent, found, token = target.client("bedrock-agent"), [], None
    while True:
        arguments = {"knowledgeBaseId": knowledge_base_id, "dataSourceId": data_source_id, "maxResults": 100}
        if token:
            arguments["nextToken"] = token
        page = agent.list_knowledge_base_documents(**arguments)
        found += [d["identifier"]["custom"]["id"] for d in page.get("documentDetails", [])]
        token = page.get("nextToken")
        if not token:
            return found


def derived_copies(target, document_ids):
    """Which of these documents still have PHYSICAL derived copies — BOTH halves of the derived-copy graph.

    Reconciliation compares an authoritative version against a reflected version, so it reported
    "15 compared · 0 missing · 0 extra · 0 divergent" while the derived store was being emptied. Version
    agreement is not evidence that a copy exists or is gone. Only the inventory is.

    Section objects AND indexed knowledge-base documents are both read, because they fail independently: in one earlier
    incident the bucket policy refused the operator's deletes while both knowledge bases were emptied, so a check of
    the buckets alone would have called that environment clean (ADR-006).
    """
    wanted, present = set(document_ids), {}
    s3 = target.client("s3")
    for output_key in ("SharedSectionBucket", "RestrictedSectionBucket"):
        page = s3.list_objects_v2(Bucket=target.outputs[output_key], Prefix="sections/")
        for entry in page.get("Contents", []):
            parts = entry["Key"].split("/")
            if len(parts) > 1 and parts[1] in wanted:
                present.setdefault(parts[1], []).append(f"object:{entry['Key']}")
    for tier in ("shared", "restricted"):
        for identifier in indexed_documents(target, tier):
            match = GENERATION_ID.match(identifier)
            if match and match.group(1) in wanted:
                present.setdefault(match.group(1), []).append(f"indexed:{identifier}")
    return {document_id: sorted(keys) for document_id, keys in present.items()}


def _wait_until_copies_gone(target, document_ids, timeout=WITHDRAW_PROPAGATION_TIMEOUT_SECONDS):
    """Wait for the change path to remove the copies, checking the inventory rather than assuming delivery happened."""
    deadline = time.monotonic() + timeout
    remaining = derived_copies(target, document_ids)
    while remaining and time.monotonic() < deadline:
        time.sleep(WITHDRAW_POLL_SECONDS)
        remaining = derived_copies(target, document_ids)
    return remaining


def withdraw_authority(target, document_ids, phases):
    """Withdraw authority and let the CHANGE PATH remove the derived copies — then prove that it actually did.

    The loader never deletes a derived copy itself and never bypasses the change path. It paces its own writes so it
    does not create the invocation burst it then trips over, waits for the ordinary stream-driven removal, and calls
    the supported apply ONLY for documents whose copies are observably still present. If none are, no explicit apply
    happens at all.
    """
    phases.enter("WITHDRAW_AUTHORITY")
    withdrawn = []
    for start in range(0, len(document_ids), LOADER_BATCH):
        for document_id in document_ids[start:start + LOADER_BATCH]:
            currency.delete_record(target, document_id)
            withdrawn.append(document_id)
        if start + LOADER_BATCH < len(document_ids):
            time.sleep(LOADER_BATCH_PAUSE_SECONDS)
    phases.complete("WITHDRAW_AUTHORITY", {"withdrawn": withdrawn, "batch_size": LOADER_BATCH,
                                           "pause_seconds": LOADER_BATCH_PAUSE_SECONDS})

    phases.enter("AWAIT_WITHDRAW_PROPAGATION")
    remaining = _wait_until_copies_gone(target, document_ids)
    phases.complete("AWAIT_WITHDRAW_PROPAGATION", {"copies_still_present": sorted(remaining)})

    phases.enter("VERIFY_WITHDRAWAL")
    stragglers = sorted(remaining)
    phases.complete("VERIFY_WITHDRAWAL", {"stragglers": stragglers})

    repaired, explicit_applies = [], 0
    if stragglers:
        phases.enter("REPAIR_WITHDRAWAL_STRAGGLERS")
        currency.apply_now(target, stragglers)          # supported change path, confirmed stragglers ONLY
        explicit_applies, repaired = 1, stragglers
        remaining = _wait_until_copies_gone(target, stragglers)
        phases.complete("REPAIR_WITHDRAWAL_STRAGGLERS",
                        {"repaired": repaired, "copies_still_present": sorted(remaining)})

    phases.enter("VERIFY_WITHDRAWAL_COMPLETE")
    if remaining:
        raise RuntimeError(f"withdrawal incomplete: derived copies remain for {sorted(remaining)} after the bounded "
                           "supported repair; refusing to restore canonical authority over unproven state")
    phases.complete("VERIFY_WITHDRAWAL_COMPLETE", {"copies_remaining": {}})
    return {"withdrawn": withdrawn, "stragglers_repaired": repaired, "explicit_applies": explicit_applies}


def special_category_sections(records):
    """Which sections the corpus says are special category — from the RECORDS, never from an apply's report.

    Read from an apply, this list is timing-dependent: when the notifier converges a document before the explicit
    apply reaches it, that apply reports DUPLICATE and contributes nothing, and the load then claims no special
    category section was excluded on a load that excluded one correctly. The records are the same whoever
    applied them, so the answer is the same on every run.
    """
    return sorted(f"{document_id}-{section['section_id']}"
                  for document_id, record in records.items()
                  for section in record.get("sections", []) if section.get("special_category"))


def derived_state_rows(rows, document_ids):
    """The convergence rows belonging to these documents — the ONLY rows a reset may remove."""
    wanted = set(document_ids)
    return [row for row in rows
            if row.get("document_id") in wanted and str(row.get("pk", "")).split("#", 1)[0] in DERIVED_PREFIXES]


def reset_derived_state(target, document_ids):
    """Remove these documents' derived state so the change path can build it again from nothing.

    A canonical reload sets authority BACK to its starting version. That is a backwards transition, and the promotion
    boundary refuses it (AB-14) — correctly, because before that fix such a reload would have walked derived state
    backwards silently. So a reload is expressed as a RESET rather than as a change: remove the bookkeeping that
    points at the old generations, and let the ordinary change path converge each document from nothing.

    This only ever REMOVES. Nothing here writes a generation, a reflected row or a serving pointer, so no fixture path
    can fabricate derived state the change path did not build — which is the property that keeps the loader honest.

    THE OPERATOR NEVER REMOVES A DERIVED COPY ITSELF. An earlier version of this function deleted knowledge-base
    documents and section objects directly, and it emptied both knowledge bases: the section buckets refused it (their
    policy admits only the change role) but knowledge-base document deletion has no equivalent resource policy, so the
    operator could do what the architecture intends only the change path to do. Removing copies belongs to the change
    path, which proves absence by reading the stores back (ADR-006, AB-13). This function clears BOOKKEEPING ONLY, and
    must be paired with a supported removal of the copies — otherwise an orphaned generation stays retrievable and two
    versions of a document can be candidates at once (FRS-003).
    """
    ddb = target.client("dynamodb")
    rows = [row for items in currency.convergence_state(target).values() for row in items]
    removing = derived_state_rows(rows, document_ids)
    removed = {"documents": sorted(set(document_ids)), "rows": []}
    for row in removing:
        # No swallowed failures: a reset that silently half-worked is how the index was emptied without anyone seeing.
        ddb.delete_item(TableName=target.outputs["ConvergenceTable"], Key={"pk": {"S": row["pk"]}})
        removed["rows"].append(row["pk"])
    removed["rows"] = sorted(set(removed["rows"]))
    return removed


def load(target, identities, reset=True):
    """Bring the deployment to canonical fixture state — and record WHERE it got to when it cannot.

    **This is not atomic and must never be described as such.** It makes many authoritative changes that the change
    path converges asynchronously, so an interruption leaves real partial state behind. What it does provide is
    FAILED LOAD → OBSERVABLE PARTIAL STATE → SAFE SUPPORTED RESUMPTION → CANONICAL STATE: every phase reads the
    deployment before acting, so a later run resumes from whatever is actually there, with no hand-made
    authoritative or derived state in between.
    """
    phases = LoaderPhases()
    try:
        return dict(_load(target, identities, reset, phases), phases=phases.completed,
                    invocations=list(currency.INVOKE_DIAGNOSTICS))
    except Exception as error:
        report = dict(phases.report(error), invocations=list(currency.INVOKE_DIAGNOSTICS))
        os.makedirs(canaries.common.RESULTS, exist_ok=True)
        stamp = rs.now_iso().replace(":", "").replace("-", "")
        with open(results_path(f"fixture-load-incomplete-{stamp}.json"), "w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2, sort_keys=True)
        raise


def _load(target, identities, reset, phases):
    s3, ddb = target.client("s3"), target.client("dynamodb")
    records = {d: with_lifecycle(r) for d, r in canaries.records().items()}
    # A reload must leave NO derived copy behind, and clearing bookkeeping FIRST strands them. Both cleanup
    # mechanisms — the retirement sweep and the deletion walk — can only act on generations the convergence store
    # still records, so a reset that runs first destroys the very record the system needs to clean up after itself.
    # Done in that order, a reload stranded an INDEXED generation of D-06 while derived state served another version:
    # two versions of one document retrievable at once (FRS-003). So withdraw authority first and let the CHANGE PATH
    # remove every generation's copies and prove absence (ADR-006, AB-13); only then clear the residual bookkeeping.
    phases.enter("PREFLIGHT")
    # What remains to be done is decided from OBSERVED AWS state, never from an assumption that this load starts from
    # canonical state. A previous load may have stopped after deleting authority, after removing some copies, or
    # after clearing bookkeeping. This is not atomic and is not claimed to be: the property is that a failed load
    # leaves an observable partial state which a later supported load can converge, without anyone hand-making
    # authoritative or derived state.
    reflected_before = currency.reflected(target)
    copies_before = derived_copies(target, sorted(records))
    held = sorted({d for d in records if reflected_before.get(d)} | set(copies_before))
    phases.complete("PREFLIGHT", {"documents": len(records), "held": held,
                                  "documents_with_derived_copies": sorted(copies_before),
                                  "resumed": not held and bool(reflected_before or copies_before)})
    reset_report = None
    if reset:
        withdrawal = (withdraw_authority(target, held, phases) if held else
                      {"withdrawn": [], "stragglers_repaired": [], "explicit_applies": 0,
                       "note": "nothing was held: withdrawal was already complete, so this load resumes from there"})
        phases.enter("RESET_BOOKKEEPING")
        reset_report = dict(reset_derived_state(target, sorted(records)), **withdrawal)
        phases.complete("RESET_BOOKKEEPING", {"rows_removed": len(reset_report.get("rows") or [])})
    phases.enter("RESTORE_AUTHORITY")
    # Paced for the same reason the withdrawal is: each authoritative write is a stream event, and fifteen at once is
    # fifteen notifier invocations competing with the explicit apply that follows — the exact burst that throttled
    # this loader. A recovery-tool operating value, not an architectural benchmark: nothing here measures
    # what the change path can sustain, and notification delivery is left alone.
    ordered = sorted(records)
    for start in range(0, len(ordered), LOADER_BATCH):
        for document_id in ordered[start:start + LOADER_BATCH]:
            s3.put_object(Bucket=target.outputs["RecordsBucket"], Key=f"records/{document_id}.md",
                          Body=canaries.markdown(document_id).encode(), ContentType="text/markdown; charset=utf-8")
            put_classification(ddb, target.outputs["RecordsTable"], records[document_id])
        if start + LOADER_BATCH < len(ordered):
            time.sleep(LOADER_BATCH_PAUSE_SECONDS)
    subjects = {}
    for name, persona in sorted(canaries.personas().items()):
        subject = identities.ensure_user(persona["username"], identities.group_names(persona))
        subjects[name] = subject
        if persona["registered"]:
            put_grants(ddb, target.outputs["AuthorizationTable"], subject, persona)

    phases.complete("RESTORE_AUTHORITY", {"documents": len(records), "personas": len(subjects)})
    phases.enter("REBUILD_DERIVED_STATE")
    report = apply_documents(target, sorted(records))
    proven = currency.converge(target, sorted(records), run_id="rec-fixture-load")
    applied = {a["document_id"]: a for a in report.get("applied", [])}
    # What the load ACHIEVED, read back from the stores — not what the explicit apply returned. The records table has
    # a stream, so the notifier converges each document as it is written; when it wins that race the explicit apply
    # finds the work already done and reports DUPLICATE. Reporting its return value made a correct load look like a
    # failed one. `applied`/`skipped` are kept below as what that one call saw, never as the evidence.
    reflected_now = currency.reflected(target)
    converged = sorted(d for d, record in records.items()
                       if int((reflected_now.get(d) or {}).get("version") or 0) == int(record["version"]))
    phases.complete("REBUILD_DERIVED_STATE", {"applied": sorted(applied), "failed": report.get("failed", [])})
    phases.enter("VERIFY_CANONICAL_STATE")
    special_category = special_category_sections(records)
    not_converged = sorted(set(records) - set(converged))
    copies_after = derived_copies(target, sorted(records))
    # The phase completes only when its postcondition holds. The derived-copy inventory is carried alongside because
    # version agreement alone is not canonical health: "15 compared · 0 missing · 0 extra · 0 divergent" is exactly
    # what reconciliation reported while the derived store was empty (AB-16).
    if not not_converged:
        phases.complete("VERIFY_CANONICAL_STATE", {"converged": len(converged),
                                                   "documents_with_derived_copies": sorted(copies_after)})
        phases.complete("COMPLETE", None)
    return {"documents": len(records), "personas": len(subjects), "reset": reset_report,
            "canonical": phases.current is None,
            "derived_copies_after": {d: len(k) for d, k in sorted(copies_after.items())},
            "converged": converged, "not_converged": not_converged,
            "applied": sorted(applied), "failed": report.get("failed", []),
            "sections": {d: a["sections"] for d, a in sorted(applied.items())},
            "quarantine": [q for a in applied.values() for q in a.get("quarantine", [])],
            "special_category_excluded": special_category,
            "special_category_excluded_by_this_apply": sorted({s for a in applied.values()
                                                               for s in a.get("special_category_excluded", [])}),
            "reconciliation": {k: proven["reconciliation"].get(k)
                               for k in ("run_id", "documents_compared", "missing", "extra", "divergent")},
            "watermarks": proven["watermarks_after"], "pending_after_load": proven["pending_after"]}


def subjects(identities):
    return {name: identities.subject(p["username"]) for name, p in canaries.personas().items()}


def results_path(*parts):
    return os.path.join(canaries.common.RESULTS, *parts)
