"""Ingestion attribution (CTL-001, CTL-011, CTL-012, CTL-013, CTL-014; ADR-004). Used by the ingestion service only.

    VERIFIED TENANT → SERVER-GENERATED DOCUMENT ID → SERVER-DERIVED STORAGE LOCATION
    → OWNERSHIP RECORD → ATTRIBUTION GATE → ATTRIBUTED INDEXING

The caller never supplies the owner, the document ID or the storage location (platform finding CH-11: the knowledge
base reads whatever S3 location it is given, so the location must come from the trusted tenant context).
Ownership is immutable: every status update is conditional on the recorded owner and never sets the owner.
"""
import re
from datetime import datetime, timezone

from shared.dynamo import to_item
from shared.registry import document_key as record_key
from shared.tenant_claims import is_tenant_id

RECEIVED, INDEXING, AVAILABLE, QUARANTINED, FAILED, DELETING, DELETED = (
    "RECEIVED", "INDEXING", "AVAILABLE", "QUARANTINED", "FAILED", "DELETING", "DELETED")
_KEY_PATTERN = re.compile(r"tenants/(?P<tenant>[^/]+)/documents/(?P<document>[^/]+)/source\.md")


class AttributionConflict(Exception):
    pass


class OwnershipConflict(Exception):
    """A conditional write failed: the record does not have the expected owner or status."""


def storage_key(tenant_id, document_id):
    return f"tenants/{tenant_id}/documents/{document_id}/source.md"


def parse_storage_key(key):
    match = _KEY_PATTERN.fullmatch(key or "")
    return (match.group("tenant"), match.group("document")) if match else (None, None)


def index_attributes(tenant_id, document_id):
    """Inline metadata attached to every indexed chunk, supplied by the service from the trusted context."""
    return [
        {"key": "owning_tenant", "value": {"type": "STRING", "stringValue": tenant_id}},
        {"key": "document_id", "value": {"type": "STRING", "stringValue": document_id}},
    ]


def _attribute(attributes, name):
    values = [a["value"].get("stringValue") for a in attributes or [] if a.get("key") == name]
    return values[0] if len(values) == 1 else None


def attribution_gate(ctx, record, key, attributes):
    """CTL-012. Record owner = storage-key tenant = attribute owner = context tenant, and the IDs agree, or nothing is
    indexed. The three values come from independent places: the stored record, the key string and the attribute list."""
    key_tenant, key_document = parse_storage_key(key)
    record = record or {}
    owners = {"context": getattr(ctx, "tenant_id", None), "record": record.get("owner"), "storage_key": key_tenant,
              "attribute": _attribute(attributes, "owning_tenant")}
    document_ids = {"record": record.get("document_id"), "storage_key": key_document,
                    "attribute": _attribute(attributes, "document_id")}
    if not all(is_tenant_id(value) for value in owners.values()):
        raise AttributionConflict(f"missing or invalid owner value: {sorted(k for k, v in owners.items() if not is_tenant_id(v))}")
    if len(set(owners.values())) != 1:
        raise AttributionConflict("owner values disagree")
    if None in document_ids.values() or len(set(document_ids.values())) != 1:
        raise AttributionConflict("document identifiers disagree")


class OwnershipStore:
    """Writes to DOC# ownership records. The ingestion role may write DOC# keys only (IAM leading-key condition)."""

    def __init__(self, client, table_name):
        self._client = client
        self._table = table_name

    def create_document(self, ctx, document_id, title, key):
        record = {"pk": record_key(document_id), "item_type": "DOCUMENT", "document_id": document_id,
                  "owner": ctx.tenant_id, "uploader": ctx.user_id, "title": title, "s3_key": key, "status": RECEIVED,
                  "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
        self._client.put_item(TableName=self._table, Item=to_item(record), ConditionExpression="attribute_not_exists(pk)")
        return record

    def set_status(self, document_id, owner, new_status, allowed_from):
        values = {":owner": {"S": owner}, ":new": {"S": new_status}}
        placeholders = []
        for index, status in enumerate(allowed_from):
            values[f":from{index}"] = {"S": status}
            placeholders.append(f":from{index}")
        try:
            self._client.update_item(
                TableName=self._table, Key={"pk": {"S": record_key(document_id)}},
                UpdateExpression="SET #s = :new",
                ConditionExpression=f"#o = :owner AND #s IN ({', '.join(placeholders)})",
                ExpressionAttributeNames={"#s": "status", "#o": "owner"}, ExpressionAttributeValues=values)
        except Exception as error:  # noqa: BLE001
            if "ConditionalCheckFailed" in type(error).__name__ or "ConditionalCheckFailed" in str(error):
                raise OwnershipConflict(f"{document_id}: owner or status not as expected") from error
            raise


def index_document(agent, knowledge_base_id, data_source_id, bucket, key, attributes, document_id):
    response = agent.ingest_knowledge_base_documents(
        knowledgeBaseId=knowledge_base_id, dataSourceId=data_source_id,
        documents=[{
            "content": {"dataSourceType": "CUSTOM", "custom": {
                "customDocumentIdentifier": {"id": document_id}, "sourceType": "S3_LOCATION",
                "s3Location": {"uri": f"s3://{bucket}/{key}"}}},
            "metadata": {"type": "IN_LINE_ATTRIBUTE", "inlineAttributes": attributes},
        }])
    return [d.get("status") for d in response.get("documentDetails", [])]


def delete_from_index(agent, knowledge_base_id, data_source_id, document_id):
    agent.delete_knowledge_base_documents(
        knowledgeBaseId=knowledge_base_id, dataSourceId=data_source_id,
        documentIdentifiers=[{"dataSourceType": "CUSTOM", "custom": {"id": document_id}}])


def index_status(agent, knowledge_base_id, data_source_id, document_id):
    try:
        response = agent.get_knowledge_base_documents(
            knowledgeBaseId=knowledge_base_id, dataSourceId=data_source_id,
            documentIdentifiers=[{"dataSourceType": "CUSTOM", "custom": {"id": document_id}}])
    except Exception as error:  # noqa: BLE001
        if "ResourceNotFound" in type(error).__name__ or "ResourceNotFound" in str(error):
            return "NOT_FOUND"
        raise
    details = response.get("documentDetails") or []
    return details[0].get("status", "UNKNOWN") if details else "NOT_FOUND"
