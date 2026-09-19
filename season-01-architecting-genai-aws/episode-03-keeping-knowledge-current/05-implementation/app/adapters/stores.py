"""AWS adapters for the authoritative stores and the derived state this implementation keeps.

Episode 02's stores are unchanged: grants, classification records (now carrying the lifecycle fields of ADR-001), audit,
the simulated records system and the tier section buckets.

Episode 03 adds ONE derived store — the convergence table — holding every piece of derived operational state:

    PENDING#<document_id>            a known change that derived state has not caught up with       (ADR-002)
    REFLECTED#<document_id>          what derived state currently reflects: version, status, generation (ADR-004)
    GENERATION#<document_id>#g<v>    a generation's state: building, verified, serving, retired     (ADR-005)
    WATERMARK#<change_class>         what reconciliation has proven for that class                 (ADR-003)
    RECONCILIATION#<run_id>          one reconciliation pass, and RECONCILIATION#LAST              (ADR-003)
    DELETION#<document_id>           the content-free deletion ledger entry                         (ADR-006)

It is derived state, never authority: if it disagrees with the records system, the records system wins (ADR-001).
Every read the request path makes is CONSISTENT and per-request; nothing is cached between invocations.
"""
import json
from decimal import Decimal

from core import convergence


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
    """Authoritative employment status (record HR) and entitlements (record GRANTS), keyed by the identity subject."""

    def __init__(self, client, table):
        self._client, self._table = client, table

    def read_current(self, requester_sub):
        keys = [{"requester_sub": {"S": requester_sub}, "record": {"S": r}} for r in ("HR", "GRANTS")]
        return {item["record"]: item for item in _batch_get(self._client, self._table, keys)}


class RecordsStore:
    """The authoritative records: classification plus lifecycle (status, effective_from, supersession) — ADR-001."""

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

    def export(self):
        """Every current record, for reconciliation (ADR-003). Never used by the request path."""
        records, kwargs = {}, {"TableName": self._table, "ConsistentRead": True}
        while True:
            page = self._client.scan(**kwargs)
            for raw in page.get("Items", []):
                item = from_item(raw)
                document_id = item.get("document_id", "")
                if document_id.startswith("HISTORY#"):
                    continue
                try:
                    records[document_id] = json.loads(item["record"])
                except (KeyError, TypeError, ValueError) as error:
                    raise StoreUnavailable("RecordUnreadable") from error
            if "LastEvaluatedKey" not in page:
                return records
            kwargs["ExclusiveStartKey"] = page["LastEvaluatedKey"]


# Episode 02 called this the classification store; the name is kept so the Episode 02 modules read unchanged.
ClassificationStore = RecordsStore


class AuditStore:
    """Write-once audit items. The query role may put items; it cannot read, update or delete them."""

    def __init__(self, client, table):
        self._client, self._table = client, table

    def put(self, record):
        self._client.put_item(TableName=self._table, Item=to_item(record),
                              ConditionExpression="attribute_not_exists(request_id)")



def _pending_from(item):
    """The ONE reconstruction used by every read path.

    Two hand-written copies of this meant a field could be added to the table and silently dropped by whichever
    reader was missed. New attributes are read with `.get`, so rows written before they existed load unchanged:
    adding retry and escalation accounting needs no migration of existing PENDING# items.
    """
    return convergence.Pending(item["document_id"], item["change_class"], int(item["effective_version"]),
                               item["noticed_at"], item.get("detail"), int(item.get("attempts") or 0),
                               item.get("last_attempt_at"), item.get("escalated_at"))


class ConvergenceStore:
    """Derived operational state: pending, reflected version, generations, watermarks, reconciliation, deletion ledger.

    The request path uses read_view() only: one batched, consistent read of the candidate documents' pending entries
    and the class watermarks. A failure is never an empty result — it is "unavailable", which the request path treats
    conservatively.
    """

    PENDING, REFLECTED, GENERATION = "PENDING#", "REFLECTED#", "GENERATION#"
    WATERMARK, RECONCILIATION, DELETION = "WATERMARK#", "RECONCILIATION#", "DELETION#"

    def __init__(self, client, table):
        self._client, self._table = client, table

    # ── request path ────────────────────────────────────────────────────────────────────────────────────────────
    def read_view(self, document_ids):
        """ConvergenceView for these documents. Any read failure returns an unavailable view, never a partial one."""
        keys = [{"pk": {"S": f"{self.PENDING}{d}"}} for d in sorted(set(document_ids))]
        keys += [{"pk": {"S": f"{self.WATERMARK}{c}"}} for c in convergence.CHANGE_CLASSES]
        try:
            items = _batch_get(self._client, self._table, keys) if keys else []
        except StoreUnavailable:
            return convergence.ConvergenceView({}, {}, available=False)
        pending, watermarks = {}, {}
        for item in items:
            key = item.get("pk", "")
            if key.startswith(self.PENDING):
                pending[item["document_id"]] = _pending_from(item)
            elif key.startswith(self.WATERMARK):
                watermarks[item["change_class"]] = convergence.Watermark(
                    item["change_class"], item.get("proven_through"), item.get("reconciliation_run_id"),
                    item.get("completed_at"), int(item.get("documents_compared") or 0))
        for change_class in convergence.CHANGE_CLASSES:
            watermarks.setdefault(change_class, convergence.Watermark(change_class))
        return convergence.ConvergenceView(pending, watermarks, available=True)

    def last_reconciliation(self):
        item = self._client.get_item(TableName=self._table, ConsistentRead=True,
                                     Key={"pk": {"S": f"{self.RECONCILIATION}LAST"}}).get("Item")
        return from_item(item).get("completed_at") if item else None

    # ── change path (operator and change-path roles only) ───────────────────────────────────────────────────────
    def put_pending(self, pending):
        self._client.put_item(TableName=self._table,
                              Item=to_item({"pk": f"{self.PENDING}{pending.document_id}", **pending.stored()}))

    def record_attempt(self, document_id, at):
        """Count ONE genuine repair invocation that did not converge (FRS-004). Only the applier calls this.

        Atomic ADD, conditioned on the entry still existing. A read-modify-write would resurrect a pending entry that
        another applier cleared in between, and that resurrected entry would later be escalated as a stuck change
        which had in fact converged — a false alert manufactured by the accounting itself.
        """
        try:
            self._client.update_item(
                TableName=self._table, Key={"pk": {"S": f"{self.PENDING}{document_id}"}},
                UpdateExpression="ADD #attempts :one SET #last = :at",
                ConditionExpression="attribute_exists(pk)",
                ExpressionAttributeNames={"#attempts": "attempts", "#last": "last_attempt_at"},
                ExpressionAttributeValues={":one": {"N": "1"}, ":at": {"S": str(at)}})
        except Exception as error:  # noqa: BLE001 — the entry was cleared: it converged, so there is nothing to count
            if type(error).__name__ != "ConditionalCheckFailedException":
                raise

    def clear_pending(self, document_id):
        self._client.delete_item(TableName=self._table, Key={"pk": {"S": f"{self.PENDING}{document_id}"}})

    def pending_all(self):
        return {i["document_id"]: _pending_from(i) for i in self._scan(self.PENDING)}

    def reflected(self, document_id):
        from core.change_apply import Reflected
        item = self._client.get_item(TableName=self._table, ConsistentRead=True,
                                     Key={"pk": {"S": f"{self.REFLECTED}{document_id}"}}).get("Item")
        if not item:
            return None
        value = from_item(item)
        return Reflected(document_id, int(value.get("version") or 0), value.get("status"), value.get("generation_id"))

    def put_reflected(self, document_id, version, status, generation_id):
        self._client.put_item(TableName=self._table, Item=to_item(
            {"pk": f"{self.REFLECTED}{document_id}", "document_id": document_id, "version": int(version),
             "status": status, "generation_id": generation_id}))

    def reflected_all(self):
        return {i["document_id"]: i for i in self._scan(self.REFLECTED)}

    def put_generation(self, generation):
        self._client.put_item(TableName=self._table, Item=to_item(
            {"pk": f"{self.GENERATION}{generation.id}", **generation.item()}))

    def generations(self, document_id=None):
        prefix = f"{self.GENERATION}{document_id}#" if document_id else self.GENERATION
        return self._scan(prefix)

    def advance_watermark(self, change_class, proven_through, run_id, completed_at, documents_compared):
        """Only a completed reconciliation pass calls this (ADR-003). Notifications never do."""
        if change_class not in convergence.CHANGE_CLASSES:
            raise ValueError(f"unknown change class {change_class}")
        self._client.put_item(TableName=self._table, Item=to_item(
            {"pk": f"{self.WATERMARK}{change_class}", "change_class": change_class, "proven_through": proven_through,
             "reconciliation_run_id": run_id, "completed_at": completed_at,
             "documents_compared": int(documents_compared)}))

    def put_reconciliation(self, run_id, summary):
        item = {"pk": f"{self.RECONCILIATION}{run_id}", "run_id": run_id, **summary}
        self._client.put_item(TableName=self._table, Item=to_item(item))
        if summary.get("completed_at"):
            self._client.put_item(TableName=self._table, Item=to_item(dict(item, pk=f"{self.RECONCILIATION}LAST")))

    def reconciliations(self):
        return [i for i in self._scan(self.RECONCILIATION) if i.get("pk") != f"{self.RECONCILIATION}LAST"]

    def put_deletion(self, entry):
        self._client.put_item(TableName=self._table, Item=to_item(
            {"pk": f"{self.DELETION}{entry['document_id']}", **entry}))

    def deletions(self):
        return self._scan(self.DELETION)

    def _scan(self, prefix):
        items, kwargs = [], {"TableName": self._table, "ConsistentRead": True}
        while True:
            page = self._client.scan(**kwargs)
            for raw in page.get("Items", []):
                item = from_item(raw)
                if str(item.get("pk", "")).startswith(prefix):
                    items.append(item)
            if "LastEvaluatedKey" not in page:
                return items
            kwargs["ExclusiveStartKey"] = page["LastEvaluatedKey"]


class RecordsSource:
    """The simulated records system: synthetic source documents in a bucket."""

    def __init__(self, client, bucket):
        self._client, self._bucket = client, bucket

    def read(self, document_id):
        return self._client.get_object(Bucket=self._bucket, Key=f"records/{document_id}.md")["Body"].read().decode()


class SectionStorage:
    """The two tier section buckets. Only the change-path role may write them (bucket policies)."""

    def __init__(self, client, buckets):
        self._client, self._buckets = client, dict(buckets)

    def uri(self, tier, key):
        return f"s3://{self._buckets[tier]}/{key}"

    def put(self, tier, key, body):
        self._client.put_object(Bucket=self._buckets[tier], Key=key, Body=body.encode("utf-8"),
                                ContentType="text/plain; charset=utf-8")

    def delete(self, tier, key):
        self._client.delete_object(Bucket=self._buckets[tier], Key=key)

    def list(self, tier, prefix="sections/"):
        keys, kwargs = [], {"Bucket": self._buckets[tier], "Prefix": prefix}
        while True:
            page = self._client.list_objects_v2(**kwargs)
            keys += [o["Key"] for o in page.get("Contents", [])]
            if not page.get("IsTruncated"):
                return keys
            kwargs["ContinuationToken"] = page["NextContinuationToken"]
