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
