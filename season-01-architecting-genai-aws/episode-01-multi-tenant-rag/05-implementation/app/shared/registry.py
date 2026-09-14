"""Read access to the tenant registry and ownership records (one table, item types TENANT#<id> and DOC#<id>).

Reads are strongly consistent. Any read failure raises RegistryUnavailable, and callers turn that into a fail-closed
refusal — an unreadable registry never means "allow".
"""
from shared.dynamo import from_item


class RegistryUnavailable(Exception):
    pass


def tenant_key(tenant_id):
    return f"TENANT#{tenant_id}"


def document_key(document_id):
    return f"DOC#{document_id}"


class Registry:
    def __init__(self, client, table_name):
        self._client = client
        self._table = table_name

    def _get(self, key):
        try:
            response = self._client.get_item(TableName=self._table, Key={"pk": {"S": key}}, ConsistentRead=True)
        except Exception as error:  # noqa: BLE001 — every failure is "unavailable", never "absent"
            raise RegistryUnavailable(type(error).__name__) from error
        item = response.get("Item")
        return from_item(item) if item else None

    def get_tenant(self, tenant_id):
        return self._get(tenant_key(tenant_id))

    def get_document(self, document_id):
        return self._get(document_key(document_id))

    def get_documents(self, document_ids):
        """Return {document_id: record} for the IDs that exist. Missing IDs are simply absent from the result."""
        wanted = sorted(set(document_ids))
        found = {}
        for start in range(0, len(wanted), 100):
            keys = [{"pk": {"S": document_key(d)}} for d in wanted[start:start + 100]]
            request = {self._table: {"Keys": keys, "ConsistentRead": True}}
            for _ in range(4):
                try:
                    response = self._client.batch_get_item(RequestItems=request)
                except Exception as error:  # noqa: BLE001
                    raise RegistryUnavailable(type(error).__name__) from error
                for item in response.get("Responses", {}).get(self._table, []):
                    record = from_item(item)
                    found[record["document_id"]] = record
                request = response.get("UnprocessedKeys") or {}
                if not request:
                    break
            if request:
                raise RegistryUnavailable("unprocessed keys after retries")
        return found
