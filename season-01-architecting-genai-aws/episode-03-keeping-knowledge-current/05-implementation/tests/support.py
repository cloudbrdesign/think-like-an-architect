"""Shared test support: puts app/ on the import path and provides fakes. No AWS SDK, credentials or network needed."""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
IMPLEMENTATION = os.path.dirname(HERE)
EPISODE = os.path.dirname(IMPLEMENTATION)
APP = os.path.join(IMPLEMENTATION, "app")
if APP not in sys.path:
    sys.path.insert(0, APP)

SUB_A = "11111111-2222-4333-8444-555555555555"


def record(document_id="D-03", document_label="INTERNAL", document_scope=None, version=1, sections=None):
    return {"document_id": document_id, "title": "Project Orion delivery report", "document_label": document_label,
            "document_scope": document_scope, "version": version,
            "sections": sections if sections is not None else [
                {"section_id": "S3", "title": "Lessons", "label": None, "scope": None, "special_category": False},
                {"section_id": "S4", "title": "Pricing", "label": "CONFIDENTIAL", "scope": "BID-ORION",
                 "special_category": False}]}


def event(sub=SUB_A, body=None, headers=None, claims_extra=None, query=None):
    claims = {"sub": sub, "token_use": "access", "client_id": "app", **(claims_extra or {})}
    return {"requestContext": {"authorizer": {"jwt": {"claims": claims}}}, "headers": headers or {},
            "rawQueryString": query or "", "body": json.dumps(body if body is not None else {"question": "Orion?"})}


class FakeGrants:
    def __init__(self, items=None, error=None):
        self.items, self.error, self.reads = items or {}, error, 0

    def read_current(self, sub):
        self.reads += 1
        if self.error:
            raise self.error
        return dict(self.items.get(sub, {}))


def grants_items(domains=(), cases=(), status="ACTIVE", hr_version=1, grants_version=1, employee_id="E-1001"):
    return {"HR": {"record": "HR", "employee_id": employee_id, "employment_status": status, "hr_version": hr_version},
            "GRANTS": {"record": "GRANTS", "domains": list(domains), "cases": list(cases),
                       "grants_version": grants_version}}


class FakeClassification:
    def __init__(self, records=None, error=None):
        self.records, self.error, self.reads = records or {}, error, 0

    def read_records(self, document_ids):
        self.reads += 1
        if self.error:
            raise self.error
        return {d: self.records.get(d) for d in document_ids}


class FakeAudit:
    def __init__(self, fail=False):
        self.items, self.fail = [], fail

    def put(self, item):
        if self.fail:
            raise RuntimeError("ConditionalCheckFailed")
        self.items.append(json.loads(json.dumps(item)))


class FakeAgentRuntime:
    """Returns canned results per knowledge base and records every call's filter."""

    def __init__(self, results=None, error=None):
        self.results, self.error, self.calls = results or {}, error, []

    def retrieve(self, knowledgeBaseId, retrievalQuery, retrievalConfiguration):
        self.calls.append({"kb": knowledgeBaseId, "filter": retrievalConfiguration["vectorSearchConfiguration"]["filter"]})
        if self.error:
            raise self.error
        return {"retrievalResults": list(self.results.get(knowledgeBaseId, []))}


def result(document_id, section_id, label, scope, version="1", score=0.8, text="synthetic text", chunk=None):
    return {"content": {"text": text}, "score": score,
            "metadata": {"x-amz-bedrock-kb-chunk-id": chunk or f"{document_id}-{section_id}-c1",
                         "document_id": document_id, "section_id": section_id, "label": label, "scope": scope,
                         "record_version": version}}


class FakeBedrock:
    def __init__(self, text="An answer from the sources.", error=None):
        self.text, self.error, self.calls = text, error, []

    def converse(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return {"output": {"message": {"content": [{"text": self.text}]}},
                "usage": {"inputTokens": 100, "outputTokens": 20}}


# ── Episode 03: the authoritative records and the derived state the change path keeps ───────────────────────────────
def lifecycle(document_id="D-03", version=1, status=None, effective_from=None, superseded_by=None, **kwargs):
    """A record carrying the lifecycle fields of ADR-001. `status=None` means the field is absent (Episode 02 shape)."""
    base = record(document_id=document_id, version=version, **kwargs)
    for key, value in (("status", status), ("effective_from", effective_from), ("superseded_by", superseded_by)):
        if value is not None:
            base[key] = value
    return base


class FakeRecords:
    """The authoritative records system in memory. `error` makes every read fail, which must never read as "empty"."""

    def __init__(self, records=None, error=None):
        self.records, self.error, self.exports = dict(records or {}), error, 0

    def read_records(self, document_ids):
        if self.error:
            raise self.error
        return {d: self.records.get(d) for d in document_ids}

    def export(self):
        self.exports += 1
        if self.error:
            raise self.error
        return {d: r for d, r in self.records.items() if r is not None}


class FakeConvergence:
    """Derived operational state in memory, with the same surface as adapters.stores.ConvergenceStore."""

    def __init__(self, available=True):
        self.pending, self.reflected_items, self.generation_items = {}, {}, {}
        self.watermarks, self.reconciliations, self.deletions_written = {}, [], []
        self.advances, self.available, self.last_completed = [], available, None

    # request path
    def read_view(self, document_ids):
        from core import convergence
        if not self.available:
            return convergence.ConvergenceView({}, {}, available=False)
        marks = {c: self.watermarks.get(c, convergence.Watermark(c)) for c in convergence.CHANGE_CLASSES}
        return convergence.ConvergenceView({d: p for d, p in self.pending.items() if d in set(document_ids)},
                                           marks, available=True)

    def last_reconciliation(self):
        return self.last_completed

    # change path
    def put_pending(self, pending):
        self.pending[pending.document_id] = pending

    def record_attempt(self, document_id, at):
        import dataclasses
        entry = self.pending.get(document_id)          # cleared means it converged: nothing to count
        if entry is not None:
            self.pending[document_id] = dataclasses.replace(entry, attempts=entry.attempts + 1, last_attempt_at=at)

    def clear_pending(self, document_id):
        self.pending.pop(document_id, None)

    def pending_all(self):
        return dict(self.pending)

    def reflected(self, document_id):
        return self.reflected_items.get(document_id)

    def put_reflected(self, document_id, version, status, generation_id):
        from core.change_apply import Reflected
        self.reflected_items[document_id] = Reflected(document_id, int(version), status, generation_id)

    def reflected_all(self):
        return {d: {"document_id": d, "version": r.version, "status": r.status, "generation_id": r.generation_id}
                for d, r in self.reflected_items.items()}

    def put_generation(self, generation):
        self.generation_items[generation.id] = generation.item()

    def generations(self, document_id=None):
        return [i for i in self.generation_items.values()
                if document_id is None or i["document_id"] == document_id]

    def advance_watermark(self, change_class, proven_through, run_id, completed_at, documents_compared):
        from core import convergence
        if change_class not in convergence.CHANGE_CLASSES:
            raise ValueError(change_class)
        self.advances.append((change_class, proven_through))
        self.watermarks[change_class] = convergence.Watermark(change_class, proven_through, run_id, completed_at,
                                                              documents_compared)

    def put_reconciliation(self, run_id, summary):
        self.reconciliations.append(dict(summary, run_id=run_id))
        if summary.get("completed_at"):
            self.last_completed = summary["completed_at"]

    def put_deletion(self, entry):
        self.deletions_written.append(entry)

    def deletions(self):
        return list(self.deletions_written)


class FakeSource:
    def __init__(self, documents=None):
        self.documents = dict(documents or {})

    def read(self, document_id):
        return self.documents[document_id]


class FakeStorage:
    """The tier section buckets in memory. Deleting an absent key raises, as S3 would for a missing tier."""

    def __init__(self):
        self.objects = {}

    def uri(self, tier, key):
        return f"s3://{tier}-sections/{key}"

    def put(self, tier, key, body):
        self.objects[(tier, key)] = body

    def delete(self, tier, key):
        del self.objects[(tier, key)]

    def list(self, tier, prefix="sections/"):
        return sorted(k for t, k in self.objects if t == tier and k.startswith(prefix))


class FakeAgent:
    """Bedrock knowledge-base ingestion in memory: documents are INDEXED as soon as they are ingested."""

    def __init__(self, status="INDEXED"):
        self.documents, self.status, self.ingested, self.deleted = {}, status, [], []

    def ingest_knowledge_base_documents(self, knowledgeBaseId, dataSourceId, documents):
        for document in documents:
            identifier = document["content"]["custom"]["customDocumentIdentifier"]["id"]
            self.documents[(knowledgeBaseId, identifier)] = self.status
            self.ingested.append(identifier)

    def get_knowledge_base_documents(self, knowledgeBaseId, dataSourceId, documentIdentifiers):
        details = []
        for entry in documentIdentifiers:
            identifier = entry["custom"]["id"]
            details.append({"identifier": {"custom": {"id": identifier}},
                            "status": self.documents.get((knowledgeBaseId, identifier), "NOT_FOUND")})
        return {"documentDetails": details}

    def delete_knowledge_base_documents(self, knowledgeBaseId, dataSourceId, documentIdentifiers):
        for entry in documentIdentifiers:
            identifier = entry["custom"]["id"]
            if (knowledgeBaseId, identifier) not in self.documents:
                raise KeyError(identifier)
            del self.documents[(knowledgeBaseId, identifier)]
            self.deleted.append(identifier)
