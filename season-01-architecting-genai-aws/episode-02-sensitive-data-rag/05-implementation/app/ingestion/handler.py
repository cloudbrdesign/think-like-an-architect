"""Ingestion job (CTL-006 – CTL-010; boundaries B8, B9). Invoked by the operator, never through the API.

For each requested document:
  1 read the classification record from the classification store — the ONLY source of labels, scopes, versions and
    special-category marks (text that claims a classification is ignored);
  2 read the source document from the records system;
  3 validate and process (core/classification.py, core/sections.py): invalid classification → quarantine;
    special-category sections → dropped before anything is written;
  4 write one object per section to its tier's section bucket (core/tier_selection.py, ingestion/tier_router.py);
  5 ingest those objects into that tier's knowledge base with inline attributes, one knowledge base at a time, and wait
    until they are indexed.
The report (and the audit item it is stored as) holds identifiers, reason codes and counts — never text.
"""
import os
import re
import time
import uuid

from core import sections
from core.audit_record import SCHEMA
from core.tier_selection import RESTRICTED_TIER, SHARED
from ingestion import tier_router

DOCUMENT_ID = re.compile(r"^D-\d{2}$")
BATCH = 10
WAIT_SECONDS = 240
_clients = {}


def _client(name):
    if name not in _clients:
        import boto3
        _clients[name] = boto3.client(name)
    return _clients[name]


def handler(event, context):
    from adapters.stores import AuditStore, ClassificationStore, RecordsSource, SectionStorage
    env = os.environ
    return run(event,
               classification=ClassificationStore(_client("dynamodb"), env["CLASSIFICATION_TABLE"]),
               records=RecordsSource(_client("s3"), env["RECORDS_BUCKET"]),
               storage=SectionStorage(_client("s3"), {SHARED: env["SHARED_SECTION_BUCKET"],
                                                     RESTRICTED_TIER: env["RESTRICTED_SECTION_BUCKET"]}),
               agent=_client("bedrock-agent"),
               knowledge_bases={SHARED: (env["SHARED_KNOWLEDGE_BASE_ID"], env["SHARED_DATA_SOURCE_ID"]),
                                RESTRICTED_TIER: (env["RESTRICTED_KNOWLEDGE_BASE_ID"], env["RESTRICTED_DATA_SOURCE_ID"])},
               audit=AuditStore(_client("dynamodb"), env["AUDIT_TABLE"]),
               deployment=env["DEPLOYMENT_NAME"])


def run(event, classification, records, storage, agent, knowledge_bases, audit, deployment, sleep=time.sleep):
    from adapters import build_info
    run_id = str(uuid.uuid4())
    document_ids = [d for d in (event or {}).get("document_ids", []) if isinstance(d, str) and DOCUMENT_ID.match(d)]
    report = {"request_id": f"ingest-{run_id}", "schema": SCHEMA, "record_type": "INGESTION_REPORT",
              "deployment": deployment, "variant": build_info.VARIANT, "documents": document_ids, "quarantine": [],
              "special_category_excluded": [], "objects": {SHARED: [], RESTRICTED_TIER: []}, "index_status": {}}
    to_ingest = {SHARED: [], RESTRICTED_TIER: []}
    for document_id in document_ids:
        try:
            record = classification.read_records([document_id])[document_id]
        except Exception:  # noqa: BLE001
            report["quarantine"].append({"document_id": document_id, "section_id": None, "reason": "RECORD_UNREADABLE"})
            continue
        if record is None:
            report["quarantine"].append({"document_id": document_id, "section_id": None, "reason": "RECORD_MISSING"})
            continue
        try:
            markdown = records.read(document_id)
        except Exception:  # noqa: BLE001
            report["quarantine"].append({"document_id": document_id, "section_id": None, "reason": "SOURCE_UNREADABLE"})
            continue
        processed = sections.process(record, markdown)
        report["quarantine"] += [{"document_id": q.document_id, "section_id": q.section_id, "reason": q.reason}
                                 for q in processed.quarantine]
        report["special_category_excluded"] += [f"{d}-{s}" for d, s in processed.special_category_excluded]
        for obj in processed.objects:
            tier = tier_router.route(obj)
            storage.put(tier, obj.object_key, obj.body)
            to_ingest[tier].append(obj)
            report["objects"][tier].append(obj.custom_document_id)
    for tier, objects in to_ingest.items():                    # one knowledge base at a time
        knowledge_base_id, data_source_id = knowledge_bases[tier]
        for start in range(0, len(objects), BATCH):
            agent.ingest_knowledge_base_documents(knowledgeBaseId=knowledge_base_id, dataSourceId=data_source_id,
                                                  documents=[_document(storage, tier, o) for o in objects[start:start + BATCH]])
        report["index_status"].update(_wait_indexed(agent, knowledge_base_id, data_source_id, objects, sleep))
    audit.put(report)
    return report


def _document(storage, tier, obj):
    return {"content": {"dataSourceType": "CUSTOM", "custom": {
                "customDocumentIdentifier": {"id": obj.custom_document_id}, "sourceType": "S3_LOCATION",
                "s3Location": {"uri": storage.uri(tier, obj.object_key)}}},
            "metadata": {"type": "IN_LINE_ATTRIBUTE", "inlineAttributes": [
                {"key": k, "value": {"type": "STRING", "stringValue": v}} for k, v in obj.attributes().items()]}}


def _wait_indexed(agent, knowledge_base_id, data_source_id, objects, sleep):
    ids = [o.custom_document_id for o in objects]
    statuses = {}
    deadline = time.monotonic() + WAIT_SECONDS
    while ids and time.monotonic() < deadline:
        statuses = {}
        for start in range(0, len(ids), BATCH):
            response = agent.get_knowledge_base_documents(knowledgeBaseId=knowledge_base_id, dataSourceId=data_source_id,
                                                          documentIdentifiers=[{"dataSourceType": "CUSTOM",
                                                                                "custom": {"id": i}}
                                                                               for i in ids[start:start + BATCH]])
            statuses.update({d["identifier"]["custom"]["id"]: d["status"] for d in response["documentDetails"]})
        if len(statuses) == len(ids) and all(s in ("INDEXED", "FAILED", "IGNORED", "METADATA_UPDATE_FAILED")
                                             for s in statuses.values()):
            break
        sleep(5)
    return statuses
