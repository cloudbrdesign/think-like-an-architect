"""Observation points (VALIDATION_PLAN section 3). Everything here uses operator credentials and is PRIVILEGED.

OP-2 audit records · OP-3 ownership records · OP-4 index status · OP-7 logs and model-logging configuration, plus the
operator-scoped retrieval used ONLY for non-vacuity preconditions (does the other tenant's target document exist and
rank for this question under that tenant's own constraint?).
"""
import time

import harness.common  # noqa: F401  (sets the import path for the application's shared modules)
from shared import ownership
from shared.dynamo import from_item, to_item


class Observer:
    def __init__(self, target):
        self.t = target
        self.ddb = target.client("dynamodb")
        self.outputs = target.outputs

    # OP-2
    def audit(self, event_id, attempts=5):
        for _ in range(attempts):
            item = self.ddb.get_item(TableName=self.outputs["AuditTable"], Key={"event_id": {"S": event_id}},
                                     ConsistentRead=True).get("Item")
            if item:
                return from_item(item)
            time.sleep(1)
        return None

    def audit_for_request(self, request_id):
        found, kwargs = [], {"TableName": self.outputs["AuditTable"], "FilterExpression": "request_id = :r",
                             "ExpressionAttributeValues": {":r": {"S": request_id}}, "ConsistentRead": True}
        while True:
            page = self.ddb.scan(**kwargs)
            found += [from_item(i) for i in page.get("Items", [])]
            if "LastEvaluatedKey" not in page:
                return found
            kwargs["ExclusiveStartKey"] = page["LastEvaluatedKey"]

    # OP-3
    def registry_get(self, key):
        item = self.ddb.get_item(TableName=self.outputs["RegistryTable"], Key={"pk": {"S": key}}, ConsistentRead=True).get("Item")
        return from_item(item) if item else None

    def registry_put(self, record):
        self.ddb.put_item(TableName=self.outputs["RegistryTable"], Item=to_item(record))

    def registry_delete(self, key):
        self.ddb.delete_item(TableName=self.outputs["RegistryTable"], Key={"pk": {"S": key}})

    def set_tenant_status(self, tenant_id, status):
        self.ddb.update_item(TableName=self.outputs["RegistryTable"], Key={"pk": {"S": f"TENANT#{tenant_id}"}},
                             UpdateExpression="SET #s = :s", ExpressionAttributeNames={"#s": "status"},
                             ExpressionAttributeValues={":s": {"S": status}})

    def document_records(self):
        records, kwargs = [], {"TableName": self.outputs["RegistryTable"], "ConsistentRead": True,
                               "FilterExpression": "item_type = :d", "ExpressionAttributeValues": {":d": {"S": "DOCUMENT"}}}
        while True:
            page = self.ddb.scan(**kwargs)
            records += [from_item(i) for i in page.get("Items", [])]
            if "LastEvaluatedKey" not in page:
                return records
            kwargs["ExclusiveStartKey"] = page["LastEvaluatedKey"]

    # OP-4
    def index_status(self, document_id):
        return ownership.index_status(self.t.client("bedrock-agent"), self.outputs["KnowledgeBaseId"],
                                      self.outputs["DataSourceId"], document_id)

    # Non-vacuity precondition (privileged, recorded)
    def operator_retrieve(self, tenant_id, question):
        response = self.t.client("bedrock-agent-runtime").retrieve(
            knowledgeBaseId=self.outputs["KnowledgeBaseId"], retrievalQuery={"text": question},
            retrievalConfiguration={"vectorSearchConfiguration": {
                "numberOfResults": 5, "filter": {"equals": {"key": "owning_tenant", "value": tenant_id}}}})
        return [((r.get("metadata") or {}).get("document_id"), (r.get("metadata") or {}).get("owning_tenant"))
                for r in response.get("retrievalResults", [])]

    # OP-7
    def log_groups(self):
        prefix = self.t.names["prefix"]
        return [f"/aws/lambda/{prefix}-query", f"/aws/lambda/{prefix}-ingestion", f"/tla/{prefix}/api-access"]

    def log_hits(self, phrases, start_ms):
        logs = self.t.client("logs")
        hits = {}
        for group in self.log_groups():
            for phrase in phrases:
                count, kwargs = 0, {"logGroupName": group, "startTime": start_ms, "filterPattern": f'"{phrase}"'}
                try:
                    while True:
                        page = logs.filter_log_events(**kwargs)
                        count += len(page.get("events", []))
                        if not page.get("nextToken"):
                            break
                        kwargs["nextToken"] = page["nextToken"]
                except logs.exceptions.ResourceNotFoundException:
                    pass
                if count:
                    hits[f"{group} :: {phrase}"] = count
        return hits

    def log_event_count(self, start_ms):
        logs, total = self.t.client("logs"), 0
        for group in self.log_groups():
            try:
                kwargs = {"logGroupName": group, "startTime": start_ms}
                while True:
                    page = logs.filter_log_events(**kwargs)
                    total += len(page.get("events", []))
                    if not page.get("nextToken"):
                        break
                    kwargs["nextToken"] = page["nextToken"]
            except logs.exceptions.ResourceNotFoundException:
                pass
        return total

    def model_invocation_logging_enabled(self):
        config = self.t.client("bedrock").get_model_invocation_logging_configuration().get("loggingConfig") or {}
        return bool(config.get("cloudWatchConfig") or config.get("s3Config"))
