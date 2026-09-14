"""Allowlisted request bodies (CTL-004, CTL-011, CTL-016).

Each route accepts only its documented fields. Any other field — including tenant_id, owning_tenant, owner or
document_id — is refused with REQUEST_FIELD_REJECTED, so a caller cannot even attempt to choose a tenant, an owner or a
document identifier. Query strings and headers are never read by the application.
"""
import base64
import json
import re

from shared.reason_codes import DOCUMENT_NOT_FOUND_FOR_TENANT, REQUEST_FIELD_REJECTED, Denied

ASK_FIELDS = {"question": 1_000}                        # characters
UPLOAD_FIELDS = {"title": 120, "content": 200_000}      # characters; content also ≤ 200 KB as UTF-8
DOCUMENT_ID_PATTERN = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}")


def _json_body(event):
    raw = event.get("body")
    if raw is None or raw == "":
        return {}
    if event.get("isBase64Encoded"):
        try:
            raw = base64.b64decode(raw).decode("utf-8")
        except (ValueError, UnicodeDecodeError):
            raise Denied(REQUEST_FIELD_REJECTED, "body is not valid UTF-8") from None
    try:
        data = json.loads(raw)
    except ValueError:
        raise Denied(REQUEST_FIELD_REJECTED, "body is not JSON") from None
    if not isinstance(data, dict):
        raise Denied(REQUEST_FIELD_REJECTED, "body is not a JSON object")
    return data


def _parse(event, allowed):
    data = _json_body(event)
    unknown = sorted(set(data) - set(allowed))
    if unknown:
        raise Denied(REQUEST_FIELD_REJECTED, f"undocumented field(s): {', '.join(unknown)}")
    values = {}
    for name, max_length in allowed.items():
        value = data.get(name)
        if not isinstance(value, str) or not value.strip() or len(value) > max_length:
            raise Denied(REQUEST_FIELD_REJECTED, f"field '{name}' missing, empty, not text or too long")
        values[name] = value
    return values


def parse_ask(event):
    return _parse(event, ASK_FIELDS)["question"]


def parse_upload(event):
    values = _parse(event, UPLOAD_FIELDS)
    if len(values["content"].encode("utf-8")) > 200_000:
        raise Denied(REQUEST_FIELD_REJECTED, "content larger than 200 KB")
    return values["title"], values["content"]


def path_document_id(event):
    """The document ID from the path. A malformed ID is indistinguishable from an unknown one (no disclosure)."""
    value = (event.get("pathParameters") or {}).get("document_id")
    if not isinstance(value, str) or DOCUMENT_ID_PATTERN.fullmatch(value) is None:
        raise Denied(DOCUMENT_NOT_FOUND_FOR_TENANT, "malformed document id")
    return value
