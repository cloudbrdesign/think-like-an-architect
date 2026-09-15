"""AWS adapters for the three authoritative stores and the storage the ingestion job writes (B3, B6, B8–B10).

Every read of authorization or classification data is a CONSISTENT read made for the current request. Nothing read
here is kept between invocations: these classes hold a client and a table name, never results.
boto3 is imported lazily by the caller, so the local core and its unit tests run without the AWS SDK.
"""
import json
from decimal import Decimal


class StoreUnavailable(Exception):
    """The store could not be read completely. Callers treat this as "cannot establish", never as "empty"."""


# ── minimal DynamoDB attribute conversion (S, N, BOOL, NULL, L, M) ─────────────────────────────────────────────────
def to_attr(value):
    if value is None:
        return {"NULL": True}
    if isinstance(value, bool):
        return {"BOOL": value}
    if isinstance(value, (int, float, Decimal)):
        return {"N": str(value)}
    if isinstance(value, str):
        return {"S": value}
    if isinstance(value, (list, tuple)):
        return {"L": [to_attr(v) for v in value]}
    if isinstance(value, dict):
        return {"M": {k: to_attr(v) for k, v in value.items()}}
    raise TypeError(f"unsupported attribute type {type(value).__name__}")


def from_attr(attr):
    (kind, value), = attr.items()
    if kind == "NULL":
        return None
    if kind == "BOOL":
        return value
    if kind == "N":
        number = Decimal(value)
        return int(number) if number == number.to_integral_value() else float(number)
    if kind == "S":
        return value
    if kind == "L":
        return [from_attr(v) for v in value]
    if kind == "M":
        return {k: from_attr(v) for k, v in value.items()}
    raise TypeError(f"unsupported attribute kind {kind}")


def to_item(record):
    return {k: to_attr(v) for k, v in record.items()}


def from_item(item):
    return {k: from_attr(v) for k, v in item.items()}


def _batch_get(client, table, keys):
    try:
        response = client.batch_get_item(RequestItems={table: {"Keys": keys, "ConsistentRead": True}})
    except Exception as error:  # noqa: BLE001 — any failure means the read is not established
        raise StoreUnavailable(type(error).__name__) from error
    if response.get("UnprocessedKeys"):
        raise StoreUnavailable("UnprocessedKeys")
    return [from_item(i) for i in response.get("Responses", {}).get(table, [])]


class GrantsStore:
    """Authoritative employment status (record HR) and entitlements (record GRANTS), keyed by the identity subject.

    Teaching simplification TS-E02-02: two authorities (HR system, entitlement registry) as two record types in one
    table. History items (HR#v…, GRANTS#v…) keep earlier versions for decision reconstruction; they are never read here.
    """

    def __init__(self, client, table):
        self._client, self._table = client, table

    def read_current(self, requester_sub):
        keys = [{"requester_sub": {"S": requester_sub}, "record": {"S": r}} for r in ("HR", "GRANTS")]
        return {item["record"]: item for item in _batch_get(self._client, self._table, keys)}


class ClassificationStore:
    """Authoritative classification records (the records system's view), one item per document."""

    def __init__(self, client, table):
        self._client, self._table = client, table

    def read_records(self, document_ids):
        document_ids = sorted(set(document_ids))
        found = {}
        for start in range(0, len(document_ids), 100):
            keys = [{"document_id": {"S": d}} for d in document_ids[start:start + 100]]
            for item in _batch_get(self._client, self._table, keys):
                try:
                    found[item["document_id"]] = json.loads(item["record"])
                except (KeyError, TypeError, ValueError) as error:
                    raise StoreUnavailable("RecordUnreadable") from error
        return {d: found.get(d) for d in document_ids}


class AuditStore:
    """Write-once audit items. The query role may put items; it cannot read, update or delete them."""

    def __init__(self, client, table):
        self._client, self._table = client, table

    def put(self, record):
        self._client.put_item(TableName=self._table, Item=to_item(record),
                              ConditionExpression="attribute_not_exists(request_id)")


class RecordsSource:
    """The simulated records system (TS-E02-05): synthetic source documents in a bucket."""

    def __init__(self, client, bucket):
        self._client, self._bucket = client, bucket

    def read(self, document_id):
        return self._client.get_object(Bucket=self._bucket, Key=f"records/{document_id}.md")["Body"].read().decode()


class SectionStorage:
    """The two tier section buckets. Only the ingestion role may write them (bucket policies)."""

    def __init__(self, client, buckets):
        self._client, self._buckets = client, dict(buckets)

    def uri(self, tier, key):
        return f"s3://{self._buckets[tier]}/{key}"

    def put(self, tier, key, body):
        self._client.put_object(Bucket=self._buckets[tier], Key=key, Body=body.encode("utf-8"),
                                ContentType="text/plain; charset=utf-8")
