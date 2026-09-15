"""Observation points (TEST_HARNESS_DESIGN §1). Operator credentials: PRIVILEGED, read-only except where named.

  audit records · tier inventories (vector metadata + section bucket listings) · ingestion reports · operational logs ·
  model invocation logging configuration.
"""
import json
import re
import time

from adapters.stores import from_item

CANARY = re.compile(r"CANARY-[A-Z0-9-]+")
TIERS = {"shared": "Shared", "restricted": "Restricted"}


class Observer:
    def __init__(self, target):
        self.t = target
        self.out = target.outputs
        self.ddb = target.client("dynamodb")

    # ── audit ─────────────────────────────────────────────────────────────────────────────────────────────────────
    def audit(self, request_id, attempts=6):
        for _ in range(attempts):
            item = self.ddb.get_item(TableName=self.out["AuditTable"], Key={"request_id": {"S": request_id}},
                                     ConsistentRead=True).get("Item")
            if item:
                return from_item(item)
            time.sleep(1)
        return None

    def scan(self, table_key):
        items, kwargs = [], {"TableName": self.out[table_key], "ConsistentRead": True}
        while True:
            page = self.ddb.scan(**kwargs)
            items += [from_item(i) for i in page.get("Items", [])]
            if "LastEvaluatedKey" not in page:
                return items
            kwargs["ExclusiveStartKey"] = page["LastEvaluatedKey"]

    def audit_items(self):
        return self.scan("AuditTable")

    def ingestion_reports(self):
        return sorted((i for i in self.audit_items() if i.get("record_type") == "INGESTION_REPORT"),
                      key=lambda i: i["request_id"])

    def raw_audit_table(self):
        """The audit table exactly as stored (attribute-value form), for content scans."""
        items, kwargs = [], {"TableName": self.out["AuditTable"], "ConsistentRead": True}
        while True:
            page = self.ddb.scan(**kwargs)
            items += page.get("Items", [])
            if "LastEvaluatedKey" not in page:
                return items
            kwargs["ExclusiveStartKey"] = page["LastEvaluatedKey"]

    # ── authoritative stores (history for reconstruction) ─────────────────────────────────────────────────────────
    def grants_item(self, subject, record):
        item = self.ddb.get_item(TableName=self.out["AuthorizationTable"], ConsistentRead=True,
                                 Key={"requester_sub": {"S": subject}, "record": {"S": record}}).get("Item")
        return from_item(item) if item else None

    def classification_item(self, key):
        item = self.ddb.get_item(TableName=self.out["ClassificationTable"], ConsistentRead=True,
                                 Key={"document_id": {"S": key}}).get("Item")
        return from_item(item) if item else None

    # ── tier inventory ────────────────────────────────────────────────────────────────────────────────────────────
    def vectors(self, tier):
        s3v = self.t.client("s3vectors")
        prefix = TIERS[tier]
        vectors, kwargs = [], {"vectorBucketName": self.out[f"{prefix}VectorBucket"],
                               "indexName": self.out[f"{prefix}VectorIndex"], "returnMetadata": True, "maxResults": 500}
        while True:
            page = s3v.list_vectors(**kwargs)
            vectors += page.get("vectors", [])
            if not page.get("nextToken"):
                return vectors
            kwargs["nextToken"] = page["nextToken"]

    def section_objects(self, tier):
        bucket = self.out[f"{TIERS[tier]}SectionBucket"]
        keys, kwargs = [], {"Bucket": bucket}
        while True:
            page = self.t.client("s3").list_objects_v2(**kwargs)
            keys += [o["Key"] for o in page.get("Contents", [])]
            if not page.get("IsTruncated"):
                return keys
            kwargs["ContinuationToken"] = page["NextContinuationToken"]

    def inventory(self):
        """Every chunk in both tiers: attributes and the canaries found in its stored text."""
        result = {}
        for tier in TIERS:
            chunks = []
            for vector in self.vectors(tier):
                metadata = vector.get("metadata") or {}
                text = json.dumps(metadata)
                attributes = _custom_attributes(metadata)
                chunks.append({"vector_id": vector["key"], "document_id": attributes.get("document_id"),
                               "section_id": attributes.get("section_id"), "label": attributes.get("label"),
                               "scope": attributes.get("scope"), "record_version": attributes.get("record_version"),
                               "canaries": sorted(set(CANARY.findall(text)))})
            result[tier] = {"chunks": chunks, "section_objects": self.section_objects(tier)}
        return result

    # ── logs ──────────────────────────────────────────────────────────────────────────────────────────────────────
    def log_groups(self):
        prefix = self.t.names["prefix"]
        return [f"/aws/lambda/{prefix}-query", f"/aws/lambda/{prefix}-ingestion", f"/tla/{prefix}/api-access"]

    def log_hits(self, phrases, start_ms):
        logs = self.t.client("logs")
        hits, total = {}, 0
        for group in self.log_groups():
            kwargs = {"logGroupName": group, "startTime": start_ms}
            events = []
            try:
                while True:
                    page = logs.filter_log_events(**kwargs)
                    events += [e["message"] for e in page.get("events", [])]
                    if not page.get("nextToken"):
                        break
                    kwargs["nextToken"] = page["nextToken"]
            except logs.exceptions.ResourceNotFoundException:
                continue
            total += len(events)
            for phrase in phrases:
                count = sum(1 for m in events if phrase in m)
                if count:
                    hits[f"{group} :: {phrase}"] = count
        return hits, total

    def model_invocation_logging_enabled(self):
        config = self.t.client("bedrock").get_model_invocation_logging_configuration().get("loggingConfig") or {}
        return bool(config.get("cloudWatchConfig") or config.get("s3Config"))


def _custom_attributes(metadata):
    """Knowledge-base vectors keep custom attributes as filterable metadata; AMAZON_BEDROCK_METADATA may also hold them."""
    attributes = {k: v for k, v in metadata.items() if not k.startswith("AMAZON_BEDROCK")}
    nested = metadata.get("AMAZON_BEDROCK_METADATA")
    if isinstance(nested, str):
        try:
            nested = json.loads(nested)
        except ValueError:
            nested = None
    if isinstance(nested, dict):
        for key in ("document_id", "section_id", "label", "scope", "record_version"):
            attributes.setdefault(key, nested.get(key))
    return attributes
