"""Test support: import path for the application and in-memory fakes of the AWS clients the application uses.

The fakes implement only the calls and conditions the application makes, so component tests run with the Python
standard library alone (no AWS SDK, no network, no account).
"""
import copy
import json
import os
import sys

APP = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "05-implementation", "app")
if APP not in sys.path:
    sys.path.insert(0, os.path.abspath(APP))

from shared.dynamo import from_item, to_item  # noqa: E402

CLIENT_ID = "app-client-123"
ISSUER = "https://cognito-idp.us-east-1.amazonaws.com/us-east-1_EXAMPLE"


class ConditionalCheckFailedException(Exception):
    pass


class FakeDynamo:
    def __init__(self):
        self.tables = {}
        self.fail_get = False
        self.fail_batch = False
        self.fail_put_tables = set()
        self.calls = []

    def _table(self, name):
        return self.tables.setdefault(name, {})

    @staticmethod
    def _key(key):
        (name, attr), = key.items()
        return attr["S"]

    def seed(self, table, record, key_name="pk"):
        self._table(table)[record[key_name]] = to_item(record)

    def record(self, table, key):
        item = self._table(table).get(key)
        return from_item(item) if item else None

    def get_item(self, TableName, Key, ConsistentRead=False):
        self.calls.append(("get_item", TableName))
        if self.fail_get:
            raise TimeoutError("registry unreachable")
        item = self._table(TableName).get(self._key(Key))
        return {"Item": copy.deepcopy(item)} if item else {}

    def batch_get_item(self, RequestItems):
        self.calls.append(("batch_get_item", list(RequestItems)))
        if self.fail_batch:
            raise TimeoutError("ownership records unreachable")
        responses = {}
        for table, spec in RequestItems.items():
            responses[table] = [copy.deepcopy(self._table(table)[k["pk"]["S"]])
                                for k in spec["Keys"] if k["pk"]["S"] in self._table(table)]
        return {"Responses": responses, "UnprocessedKeys": {}}

    def put_item(self, TableName, Item, ConditionExpression=None):
        self.calls.append(("put_item", TableName))
        if TableName in self.fail_put_tables:
            raise TimeoutError("write failed")
        key_name = "event_id" if "event_id" in Item and "pk" not in Item else "pk"
        key = Item[key_name]["S"]
        if ConditionExpression and "attribute_not_exists" in ConditionExpression and key in self._table(TableName):
            raise ConditionalCheckFailedException("exists")
        self._table(TableName)[key] = copy.deepcopy(Item)

    def update_item(self, TableName, Key, UpdateExpression, ConditionExpression=None, ExpressionAttributeNames=None,
                    ExpressionAttributeValues=None):
        self.calls.append(("update_item", TableName))
        if TableName in self.fail_put_tables:
            raise TimeoutError("write failed")
        key = self._key(Key)
        item = self._table(TableName).get(key)
        names, values = ExpressionAttributeNames or {}, ExpressionAttributeValues or {}
        if ConditionExpression:
            if item is None:
                raise ConditionalCheckFailedException("missing")
            if "#o = :owner" in ConditionExpression:
                current = from_item(item)
                allowed = [v["S"] for k, v in values.items() if k.startswith(":from")]
                if current.get("owner") != values[":owner"]["S"] or current.get("status") not in allowed:
                    raise ConditionalCheckFailedException("owner or status")
        for assignment in UpdateExpression[len("SET "):].split(", "):
            name, value = [part.strip() for part in assignment.split("=")]
            item[names[name]] = values[value]


class FakeRetrieveRuntime:
    def __init__(self, results=None, error=None):
        self.results = results or []
        self.error = error
        self.calls = []

    def retrieve(self, **kwargs):
        self.calls.append(copy.deepcopy(kwargs))
        if self.error:
            raise self.error
        return {"retrievalResults": copy.deepcopy(self.results)}


class FakeConverse:
    def __init__(self, text="The rate is USD 185 per hour [D1].", error=None, on_call=None):
        self.text, self.error, self.on_call, self.calls = text, error, on_call, []

    def converse(self, **kwargs):
        self.calls.append(kwargs)
        if self.on_call:
            self.on_call()
        if self.error:
            raise self.error
        return {"output": {"message": {"content": [{"text": self.text}]}}, "usage": {"inputTokens": 10, "outputTokens": 5}}


class FakeAgent:
    def __init__(self, status="INDEXED"):
        self.ingested, self.deleted, self.status = [], [], status

    def ingest_knowledge_base_documents(self, **kwargs):
        self.ingested.append(kwargs)
        return {"documentDetails": [{"status": "STARTING"}]}

    def delete_knowledge_base_documents(self, **kwargs):
        self.deleted.append(kwargs)
        return {"documentDetails": [{"status": "DELETING"}]}

    def get_knowledge_base_documents(self, **kwargs):
        return {"documentDetails": [{"status": self.status}]}


class FakeS3:
    def __init__(self):
        self.objects, self.deleted = {}, []

    def put_object(self, Bucket, Key, Body, ContentType=None):
        self.objects[(Bucket, Key)] = Body

    def get_object(self, Bucket, Key):
        body = self.objects[(Bucket, Key)]

        class _Body:
            def read(self):
                return body
        return {"Body": _Body()}

    def delete_object(self, Bucket, Key):
        self.deleted.append((Bucket, Key))
        self.objects.pop((Bucket, Key), None)


def result(document_id, owner, text="chunk text", extra_metadata=True):
    metadata = {"document_id": document_id, "owning_tenant": owner}
    if extra_metadata:
        metadata.update({"x-amz-bedrock-kb-chunk-id": "chunk-1", "x-amz-bedrock-kb-data-source-id": "DS123"})
    return {"content": {"text": text}, "metadata": metadata, "score": 0.9,
            "location": {"type": "CUSTOM", "customDocumentLocation": {"id": document_id}}}


def api_event(groups="[tenant-a]", body=None, route="POST /ask", token_use="access", client_id=CLIENT_ID,
              query=None, headers=None, path_parameters=None, extra_claims=None):
    claims = {"sub": "user-sub-1", "token_use": token_use, "client_id": client_id, "iss": ISSUER,
              "scope": "aws.cognito.signin.user.admin"}
    if groups is not None:
        claims["cognito:groups"] = groups
    claims.update(extra_claims or {})
    return {"routeKey": route, "rawQueryString": query or "", "queryStringParameters": {"tenant": "tenant-b"} if query else None,
            "headers": headers or {}, "pathParameters": path_parameters,
            "body": json.dumps(body) if body is not None else None, "isBase64Encoded": False,
            "requestContext": {"requestId": "req-1", "authorizer": {"jwt": {"claims": claims, "scopes": None}}}}


def tenant(tenant_id, status="ENABLED"):
    return {"pk": f"TENANT#{tenant_id}", "item_type": "TENANT", "tenant_id": tenant_id, "status": status}


def document(document_id, owner, status="AVAILABLE", title="Doc"):
    return {"pk": f"DOC#{document_id}", "item_type": "DOCUMENT", "document_id": document_id, "owner": owner,
            "status": status, "title": title, "s3_key": f"tenants/{owner}/documents/{document_id}/source.md"}
