"""Change applier: the only writer of derived retrieval state (CTL-032, CTL-033, CTL-034; ADR-004, ADR-005, ADR-006).

Every change — notified, repaired by reconciliation, or part of a rebuild — is applied through this one path, so
ordering and idempotency are proved once:

    decide      core/change_apply.py    APPLY | DUPLICATE | OLDER | AFTER_DELETE, from the AUTHORITATIVE version
    build       core/sections.py        one object per section, written under this generation's keys
    verify      core/generations.py     every expected section present, with this document, section and version
    switch                              the generation becomes the serving one, in one write
    retire                              the previous generation's objects and knowledge-base documents are removed
    clear                               the pending entry is cleared — the document is current again

A deletion is applied the same way: the derived-copy graph (core/deletion.py) is walked and each copy removed, with a
content-free ledger entry recording what was proven.

Nothing here reads document text for status, and nothing here advances a watermark.
"""
import json
import os
import time

import uuid

from adapters.stores import AuditStore, ConvergenceStore, RecordsSource, RecordsStore, SectionStorage
from core import change_apply, deletion, generations, record_state, sections
from core.audit_record import SCHEMA
from core.tier_selection import RESTRICTED_TIER, SHARED, tier_for_label

BATCH = 10
WAIT_SECONDS = 240
MESSAGE_LIMIT = 200
_clients = {}


class ChangeApplicationError(RuntimeError):
    """A failure raised by this path, carrying WHERE it happened — not merely that it did.

    A bare RuntimeError told an operator only its class. When FX-2's replay failed, the recorded evidence could not
    distinguish "the generation did not verify" from "the generation never indexed", and the deployment's logs were
    destroyed with its stack before anyone could ask. The fields below are the minimum needed to name the failure site
    afterwards, and every one of them is an identifier, a version or a reason code — never document text.

    A RuntimeError subclass, so every existing caller's behaviour is unchanged: the document stays pending, the failure
    is reported, and nothing is silently dropped.
    """

    def __init__(self, stage, reason, document_id=None, attempted_version=None, generation_id=None, detail=None):
        super().__init__(f"{stage}: {reason}" + (f" ({detail})" if detail else ""))
        self.stage, self.reason, self.document_id = stage, reason, document_id
        self.attempted_version, self.generation_id, self.detail = attempted_version, generation_id, detail

    def fields(self):
        return {"stage": self.stage, "reason": self.reason, "attempted_version": self.attempted_version,
                "generation_id": self.generation_id, "detail": self.detail}


def _client(name):
    if name not in _clients:
        import boto3
        _clients[name] = boto3.client(name)
    return _clients[name]


def services_from_environment():
    env = os.environ
    return {
        "records": RecordsStore(_client("dynamodb"), env["RECORDS_TABLE"]),
        "source": RecordsSource(_client("s3"), env["RECORDS_BUCKET"]),
        "storage": SectionStorage(_client("s3"), {SHARED: env["SHARED_SECTION_BUCKET"],
                                                  RESTRICTED_TIER: env["RESTRICTED_SECTION_BUCKET"]}),
        "convergence_store": ConvergenceStore(_client("dynamodb"), env["CONVERGENCE_TABLE"]),
        "audit": AuditStore(_client("dynamodb"), env["AUDIT_TABLE"]),
        "agent": _client("bedrock-agent"),
        "knowledge_bases": {SHARED: (env["SHARED_KNOWLEDGE_BASE_ID"], env["SHARED_DATA_SOURCE_ID"]),
                            RESTRICTED_TIER: (env["RESTRICTED_KNOWLEDGE_BASE_ID"], env["RESTRICTED_DATA_SOURCE_ID"])},
        "deployment": env["DEPLOYMENT_NAME"],
    }


def handler(event, context):
    return run(event, **services_from_environment())


def run(event, records, source, storage, convergence_store, agent, knowledge_bases, deployment, audit=None,
        sleep=time.sleep, now=None):
    """`event`: {"document_ids": [...]} or {"all_pending": true}. Returns a content-free report."""
    document_ids = [d for d in (event or {}).get("document_ids", []) if isinstance(d, str)]
    if (event or {}).get("all_pending"):
        document_ids = sorted(set(document_ids) | set(convergence_store.pending_all()))
    report = {"record_type": "CHANGE_APPLICATION", "deployment": deployment, "documents": sorted(document_ids),
              "applied": [], "skipped": [], "deleted": [], "failed": []}
    current = records.read_records(document_ids) if document_ids else {}
    for document_id in sorted(document_ids):
        try:
            outcome = apply_one(document_id, current.get(document_id), records, source, storage, convergence_store,
                                agent, knowledge_bases, sleep, now)
        except Exception as error:  # noqa: BLE001 — a failed document stays pending and is reported, never silent
            # The versions are read here rather than inside the raise, so an SDK error gets the same context as ours.
            failure = _failure(document_id, error, current.get(document_id),
                               _reflected_quietly(convergence_store, document_id))
            # One GENUINE repair invocation that did not converge (FRS-004). The reconciler cannot count this: it
            # invokes the applier with InvocationType="Event" and never learns the outcome. Counting its own
            # observations of divergence instead would inflate the number without a single attempt behind it.
            try:
                convergence_store.record_attempt(document_id, record_state.now_iso())
            except Exception as accounting:  # noqa: BLE001 — accounting must never mask the failure it is counting
                failure["attempt_accounting"] = type(accounting).__name__
            report["failed"].append(failure)
            print(json.dumps({"stage": "apply", "outcome": "FAILED", **failure}, sort_keys=True))
            continue
        report[outcome.pop("bucket")].append(outcome)
    # What was refused entry to the index, aggregated for the run — the same evidence Episode 02's ingestion reported.
    report["quarantine"] = [q for a in report["applied"] for q in a.get("quarantine", [])]
    report["special_category_excluded"] = sorted({s for a in report["applied"]
                                                  for s in a.get("special_category_excluded", [])})
    if audit is not None:
        # The change path's own record. Identifiers, reason codes and counts only — never text (SEC-005, §18).
        audit.put({"request_id": f"chg-{uuid.uuid4()}", "schema": SCHEMA, "timestamp": record_state.now_iso(),
                   **report})
    print(json.dumps({"stage": "apply", "applied": len(report["applied"]), "skipped": len(report["skipped"]),
                      "deleted": len(report["deleted"]), "failed": len(report["failed"])}, sort_keys=True))
    return report


def _failure(document_id, error, record=None, reflected=None, now=None):
    """A content-free failure record that says WHAT failed and WHERE, not merely that something did (FRS-004, OPS-001).

    "A change was recorded as failed" is only useful to an operator if the record names the site, the versions in play
    and the reason. Keeping only the exception class once made a real, reproducible failure undiagnosable after its
    environment was cleaned up: two different raises in the build path are both `RuntimeError`, and nothing recorded
    said which one fired.

    What is kept: the exception class, a bounded message, the AWS code and operation where there is one, the stage,
    the document, the version that was being applied, the version currently serving, the generation identity, and when
    it happened. Identifiers, versions and reason codes only — the message is capped and stripped of line breaks, and
    the change path's exceptions are raised either here or by the SDK, so none of them carries document text.
    """
    response = getattr(error, "response", None)
    code = (response or {}).get("Error", {}).get("Code") if isinstance(response, dict) else None
    attempted = record.get("version") if isinstance(record, dict) else None
    failure = {"document_id": document_id, "error": type(error).__name__, "code": code,
               "operation": getattr(error, "operation_name", None), "message": _safe_message(error),
               "stage": None, "reason": None, "attempted_version": attempted,
               "serving_version": getattr(reflected, "version", None),
               "serving_generation_id": getattr(reflected, "generation_id", None),
               "generation_id": None, "detail": None, "at": now or record_state.now_iso()}
    if isinstance(error, ChangeApplicationError):
        fields = error.fields()
        failure.update({k: v for k, v in fields.items() if v is not None or k in ("stage", "reason")})
        if fields.get("attempted_version") is None:
            failure["attempted_version"] = attempted
    return failure


def _safe_message(error):
    """The exception's own words, bounded and single-line, so a diagnosis survives without becoming a content channel."""
    text = " ".join(str(error).split())
    return text[:MESSAGE_LIMIT] if text else None


def _reflected_quietly(convergence_store, document_id):
    """What derived state currently serves, for the failure record only.

    Read defensively: this runs while a failure is already being recorded, and a convergence store that is itself
    unavailable must not replace the original error with a second one. Absent context is recorded as absent.
    """
    try:
        return convergence_store.reflected(document_id)
    except Exception:  # noqa: BLE001 — context is best-effort; the failure being recorded is the thing that matters
        return None


def apply_one(document_id, record, records, source, storage, convergence_store, agent, knowledge_bases, sleep=time.sleep,
              now=None):
    """Apply one document's authoritative state to derived state. Returns a content-free outcome."""
    state = record_state.parse(document_id, record) if record is not None else record_state.RecordState(
        document_id, 0, record_state.DELETED)
    reflected = convergence_store.reflected(document_id)
    incoming_version = state.version if state.version else (reflected.version + 1 if reflected else 1)
    decision = change_apply.decide(reflected, incoming_version, state.status)

    if decision in (change_apply.DUPLICATE, change_apply.OLDER, change_apply.AFTER_DELETE):
        # Duplicates are no-ops; older arrivals and post-deletion changes are recorded as rejected, never applied.
        if decision == change_apply.DUPLICATE and state.servable:
            convergence_store.clear_pending(document_id)
        return {"bucket": "skipped", **change_apply.rejection(document_id, decision,
                                                              reflected.version if reflected else 0, incoming_version)}

    if not state.servable:
        return {"bucket": "deleted", **_remove(document_id, state, storage, convergence_store, agent, knowledge_bases,
                                               sleep, now)}
    return {"bucket": "applied", **_build_and_switch(document_id, record, state, source, storage, convergence_store,
                                                     agent, knowledge_bases, sleep)}


def _build_and_switch(document_id, record, state, source, storage, convergence_store, agent, knowledge_bases, sleep):
    """BUILD → VERIFY → SWITCH → RETIRE. A failure leaves the previous generation serving and the document pending."""
    markdown = source.read(document_id)
    processed = sections.process(record, markdown)
    if not processed.objects:
        # Nothing from this record may be indexed: its classification is invalid, or every section is special
        # category. That is a deliberate, terminal outcome (CTL-007, CTL-009) — NOT a change still waiting to be
        # applied. Recording it as reflected keeps the document out of the pending set and out of reconciliation's
        # "missing" list, instead of queueing for ever a repair that can never succeed.
        convergence_store.put_reflected(document_id, state.version, change_apply.QUARANTINED, None)
        convergence_store.clear_pending(document_id)
        return {"document_id": document_id, "generation_id": None, "version": state.version, "sections": 0,
                "retired": None, "indexed": False,
                "special_category_excluded": [f"{d}-{s}" for d, s in processed.special_category_excluded],
                "quarantine": [{"document_id": q.document_id, "section_id": q.section_id, "reason": q.reason}
                               for q in processed.quarantine]}

    written, by_tier = {}, {SHARED: [], RESTRICTED_TIER: []}
    for obj in processed.objects:
        key = generations.object_key(document_id, obj.section_id, state.version)
        storage.put(obj.tier, key, obj.body)
        attributes = dict(obj.attributes(), record_version=str(state.version))
        written[obj.section_id] = attributes
        by_tier[obj.tier].append((obj, key, attributes))

    generation = generations.verify(document_id, state.version, [o.section_id for o in processed.objects], written)
    convergence_store.put_generation(generation)
    if generation.state != generations.VERIFIED:
        raise ChangeApplicationError("verify", generation.problem or "NOT_VERIFIED", document_id, state.version,
                                     generation.id)

    index_status = {}
    for tier, entries in by_tier.items():
        if not entries:
            continue
        knowledge_base_id, data_source_id = knowledge_bases[tier]
        documents = [_kb_document(storage, tier, document_id, obj, key, attributes, state.version)
                     for obj, key, attributes in entries]
        for start in range(0, len(documents), BATCH):
            agent.ingest_knowledge_base_documents(knowledgeBaseId=knowledge_base_id, dataSourceId=data_source_id,
                                                  documents=documents[start:start + BATCH])
        index_status.update(_wait_indexed(agent, knowledge_base_id, data_source_id,
                                          [d["content"]["custom"]["customDocumentIdentifier"]["id"] for d in documents],
                                          sleep))
    if any(status != "INDEXED" for status in index_status.values()):
        # Which identifiers, and what the store said about each: a generation rebuilt at a version whose documents were
        # previously deleted fails differently from one the service rejected, and the record must be able to say so.
        not_indexed = sorted(i for i, s in index_status.items() if s != "INDEXED")
        raise ChangeApplicationError("index", "NOT_FULLY_INDEXED", document_id, state.version, generation.id,
                                     detail=f"{len(not_indexed)}/{len(index_status)} "
                                            f"{sorted(set(index_status.values()))} {not_indexed[:BATCH]}")

    # THE PROMOTION BOUNDARY (AB-14). Read what is serving NOW — not what was serving when this build began — and
    # refuse to replace it with an older authoritative version. Every mechanism that can make a generation serve
    # arrives here: the incremental apply, a reconciliation repair, an operator repair and a rebuild. Rebuild reaches
    # this point WITHOUT the applier's earlier ordering decision, which is how it moved a document backwards.
    serving_now = convergence_store.reflected(document_id)
    if not change_apply.may_promote(serving_now, state.version, state.status):
        # The generation is already built and indexed by now, so remove it rather than leave a generation that will
        # never serve with its copies live in the stores — the AB-11 leak, arrived at from the other direction.
        _delete_generation(document_id, state.version, list(generation.section_ids), None, storage,
                           convergence_store, agent, knowledge_bases)
        convergence_store.put_generation(generations.Generation(document_id, state.version, generations.RETIRED,
                                                                generation.section_ids))
        raise ChangeApplicationError("promote", "WOULD_REGRESS_SERVING_STATE", document_id, state.version,
                                     generation.id,
                                     detail=f"serving version {getattr(serving_now, 'version', None)}")
    serving = generations.switch(generation, serving_now, state.status)
    convergence_store.put_generation(serving)
    convergence_store.put_reflected(document_id, state.version, state.status, serving.id)
    # Retire against what exists AT SWITCH TIME, never against what was serving when this build started. Building
    # takes seconds to minutes, and another applier — the notifier's, or a reconciliation repair — may have switched
    # in between. Retiring a remembered "previous" then leaks the generation that was actually serving, leaving two
    # generations of one document retrievable (ADR-005, FRS-003).
    retired = _retire_others(document_id, state.version, storage, convergence_store, agent, knowledge_bases)
    convergence_store.clear_pending(document_id)
    return {"document_id": document_id, "generation_id": serving.id, "version": state.version,
            "sections": len(serving.section_ids), "retired": retired,
            "special_category_excluded": [f"{d}-{s}" for d, s in processed.special_category_excluded],
            "quarantine": [{"document_id": q.document_id, "section_id": q.section_id, "reason": q.reason}
                           for q in processed.quarantine]}


def _kb_document(storage, tier, document_id, obj, key, attributes, version):
    identifier = generations.custom_document_id(document_id, obj.section_id, version)
    return {"content": {"dataSourceType": "CUSTOM", "custom": {
                "customDocumentIdentifier": {"id": identifier}, "sourceType": "S3_LOCATION",
                "s3Location": {"uri": storage.uri(tier, key)}}},
            "metadata": {"type": "IN_LINE_ATTRIBUTE", "inlineAttributes": [
                {"key": k, "value": {"type": "STRING", "stringValue": str(v)}} for k, v in attributes.items()]}}


def _wait_indexed(agent, knowledge_base_id, data_source_id, identifiers, sleep):
    statuses, deadline = {}, time.monotonic() + WAIT_SECONDS
    while identifiers and time.monotonic() < deadline:
        statuses = {}
        for start in range(0, len(identifiers), BATCH):
            response = agent.get_knowledge_base_documents(
                knowledgeBaseId=knowledge_base_id, dataSourceId=data_source_id,
                documentIdentifiers=[{"dataSourceType": "CUSTOM", "custom": {"id": i}}
                                     for i in identifiers[start:start + BATCH]])
            statuses.update({d["identifier"]["custom"]["id"]: d["status"] for d in response["documentDetails"]})
        if len(statuses) == len(identifiers) and all(s in ("INDEXED", "FAILED", "IGNORED", "METADATA_UPDATE_FAILED")
                                                     for s in statuses.values()):
            break
        sleep(5)
    return statuses


def _delete_generation(document_id, version, section_ids, record, storage, convergence_store, agent, knowledge_bases):
    """Remove one generation's derived copies. Returns {derived copy kind: (status, detail)}."""
    results = {}
    labels = {}
    if record:
        from core import classification
        classified, _ = classification.classify(record)
        labels = {section_id: section.label for section_id, section in classified.items()}
    removed_objects, removed_documents = 0, 0
    for section_id in section_ids:
        tier = tier_for_label(labels[section_id]) if section_id in labels else None
        for candidate in ([tier] if tier else [SHARED, RESTRICTED_TIER]):
            try:
                storage.delete(candidate, generations.object_key(document_id, section_id, version))
                removed_objects += 1
            except Exception:  # noqa: BLE001 — a missing object is already removed
                pass
        identifier = generations.custom_document_id(document_id, section_id, version)
        for candidate in ([tier] if tier else [SHARED, RESTRICTED_TIER]):
            knowledge_base_id, data_source_id = knowledge_bases[candidate]
            try:
                agent.delete_knowledge_base_documents(
                    knowledgeBaseId=knowledge_base_id, dataSourceId=data_source_id,
                    documentIdentifiers=[{"dataSourceType": "CUSTOM", "custom": {"id": identifier}}])
                removed_documents += 1
            except Exception:  # noqa: BLE001
                pass
    results[deletion.SECTION_OBJECT] = (deletion.DONE if removed_objects else deletion.FAILED, None)
    results[deletion.KNOWLEDGE_BASE_DOCUMENT] = (deletion.DONE if removed_documents else deletion.FAILED, None)
    # The vectors belong to the knowledge-base document: removing the document removes them (verified by the harness
    # against the vector index, not asserted here).
    results[deletion.VECTOR_ENTRY] = (deletion.DONE if removed_documents else deletion.FAILED, "with the document")
    return results


def _retire_others(document_id, current_version, storage, convergence_store, agent, knowledge_bases):
    """Retire the generations of this document that are OLDER than the one now serving (ADR-005, AB-16).

    Sweeping, rather than retiring one remembered "previous", makes retirement idempotent and self-correcting: a
    generation leaked by a concurrent apply is removed the next time the document is applied, instead of staying
    retrievable indefinitely. A rebuild at an unchanged version is safe for the same reason — the generation just
    written and verified is the serving one, and is never swept.

    But the sweep may only reach BACKWARDS. A build writes its generation and its derived copies before it switches,
    so a slower operation can see a newer generation — VERIFIED and not yet promoted, or already promoted while this
    one was still working — and destroying its artefacts leaves a serving generation with no section object, which
    reconciliation cannot detect because it compares versions (AB-16). The rule lives in `generations.may_retire`,
    beside the promotion boundary, so every path that retires goes through one definition of it.
    """
    retired = []
    for item in convergence_store.generations(document_id):
        version = int(item.get("version") or 0)
        if not version or item.get("state") == generations.RETIRED:
            continue
        if not generations.may_retire(version, current_version):
            continue
        section_ids = list(item.get("section_ids") or [])
        if section_ids:
            _delete_generation(document_id, version, section_ids, None, storage, convergence_store, agent,
                               knowledge_bases)
        convergence_store.put_generation(generations.Generation(document_id, version, generations.RETIRED,
                                                                tuple(section_ids)))
        retired.append(generations.generation_id(document_id, version))
    return sorted(retired)


def _still_present(document_id, versions, storage, agent, knowledge_bases):
    """What is STILL THERE for this document: section object keys and knowledge-base document identifiers.

    Deletion proves absence; it never infers it. A generation marked RETIRED says what the system intended, not what
    the stores contain, so the ledger is built from a reading of the stores themselves (ADR-006, §11).
    """
    objects, documents = [], []
    for tier in (SHARED, RESTRICTED_TIER):
        try:
            objects += list(storage.list(tier, f"sections/{document_id}/"))
        except Exception:  # noqa: BLE001 — an unreadable tier is not evidence of absence; it stays outstanding
            objects.append(f"{tier}:unreadable")
        knowledge_base_id, data_source_id = knowledge_bases[tier]
        identifiers = [generations.custom_document_id(document_id, section_id, version)
                       for version, section_ids in versions.items() for section_id in section_ids]
        for start in range(0, len(identifiers), BATCH):
            batch = identifiers[start:start + BATCH]
            try:
                response = agent.get_knowledge_base_documents(
                    knowledgeBaseId=knowledge_base_id, dataSourceId=data_source_id,
                    documentIdentifiers=[{"dataSourceType": "CUSTOM", "custom": {"id": i}} for i in batch])
            except Exception:  # noqa: BLE001 — the tier does not hold them (or cannot say); other tiers still checked
                continue
            documents += [d["identifier"]["custom"]["id"] for d in response.get("documentDetails", [])
                          if "DELET" not in str(d.get("status", "")) and d.get("status") != "NOT_FOUND"]
    return sorted(set(objects)), sorted(set(documents))


def _remove(document_id, state, storage, convergence_store, agent, knowledge_bases, sleep=time.sleep, now=None):
    """Deletion across the derived-copy graph, with a content-free ledger entry (ADR-006).

    EVERY generation is walked — serving, retired or otherwise — because retirement records an intention and this
    must record a fact. Absence is then read back from the stores, so "the content is gone" and "we proved the content
    is gone" are not confused with each other (AB-13).
    """
    logical_at = now or record_state.now_iso()
    versions = {int(item.get("version") or 0): list(item.get("section_ids") or [])
                for item in convergence_store.generations(document_id) if int(item.get("version") or 0)}
    for version, section_ids in sorted(versions.items()):
        _delete_generation(document_id, version, section_ids, None, storage, convergence_store, agent,
                           knowledge_bases)
        convergence_store.put_generation(generations.Generation(document_id, version, generations.RETIRED,
                                                                tuple(section_ids)))
    objects, documents = _still_present(document_id, versions, storage, agent, knowledge_bases)
    for _ in range(6):                               # removal from the index is eventually consistent (AB-10)
        if not objects and not documents:
            break
        sleep(5)
        objects, documents = _still_present(document_id, versions, storage, agent, knowledge_bases)

    results = {deletion.SECTION_OBJECT: (deletion.DONE if not objects else deletion.FAILED,
                                         None if not objects else f"{len(objects)} still present"),
               deletion.KNOWLEDGE_BASE_DOCUMENT: (deletion.DONE if not documents else deletion.FAILED,
                                                  None if not documents else f"{len(documents)} still present"),
               deletion.VECTOR_ENTRY: (deletion.DONE if not documents else deletion.FAILED, "with the document"),
               deletion.GENERATION_RECORD: (deletion.DONE, f"{len(versions)} generations retired")}
    convergence_store.clear_pending(document_id)
    results[deletion.PENDING_ENTRY] = (deletion.DONE, None)
    convergence_store.put_reflected(document_id, state.version or 0, record_state.DELETED, None)
    entry = deletion.ledger_entry(document_id, state.version or 0, state.effective_from or logical_at, logical_at,
                                 results)
    convergence_store.put_deletion(entry)
    return {"document_id": document_id, "phase": entry["phase"], "outstanding": deletion.outstanding(entry),
            "generations_walked": sorted(versions)}
