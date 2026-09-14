"""Stable, machine-observable reason codes (IMPLEMENTATION_CONTROLS section 4).

Every refusal carries one of these codes, the HTTP status the caller sees and the control that stopped the request.
The API edge codes (AUTH_TOKEN_MISSING, AUTH_TOKEN_INVALID) never reach this code: the edge rejects those requests
before any function runs, so no audit record exists for them.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Reason:
    code: str
    status: int
    failed_control: object  # str or None


ALLOWED = Reason("ALLOWED", 200, None)
REQUEST_FIELD_REJECTED = Reason("REQUEST_FIELD_REJECTED", 400, "CTL-004")
TENANT_CLAIM_MISSING = Reason("TENANT_CLAIM_MISSING", 403, "CTL-004")
TENANT_CLAIM_AMBIGUOUS = Reason("TENANT_CLAIM_AMBIGUOUS", 403, "CTL-004")
TENANT_UNKNOWN = Reason("TENANT_UNKNOWN", 403, "CTL-005")
TENANT_DISABLED = Reason("TENANT_DISABLED", 403, "CTL-005")
TENANT_REGISTRY_UNAVAILABLE = Reason("TENANT_REGISTRY_UNAVAILABLE", 503, "CTL-005")
RETRIEVAL_SCOPE_INVALID = Reason("RETRIEVAL_SCOPE_INVALID", 403, "CTL-007")
RETRIEVAL_UNAVAILABLE = Reason("RETRIEVAL_UNAVAILABLE", 503, "CTL-015")
OWNERSHIP_MISMATCH = Reason("OWNERSHIP_MISMATCH", 500, "CTL-017")
OWNERSHIP_LOOKUP_FAILED = Reason("OWNERSHIP_LOOKUP_FAILED", 503, "CTL-017")
INGESTION_ATTRIBUTION_CONFLICT = Reason("INGESTION_ATTRIBUTION_CONFLICT", 409, "CTL-012")
DOCUMENT_NOT_FOUND_FOR_TENANT = Reason("DOCUMENT_NOT_FOUND_FOR_TENANT", 404, "CTL-014")
AUDIT_WRITE_FAILED = Reason("AUDIT_WRITE_FAILED", 503, "CTL-019")
MODEL_INVOCATION_FAILED = Reason("MODEL_INVOCATION_FAILED", 502, "CTL-022")
INTERNAL_ERROR = Reason("INTERNAL_ERROR", 500, None)

# Generic messages: a refusal never explains more than the code itself (no existence disclosure).
MESSAGES = {
    "REQUEST_FIELD_REJECTED": "The request contains a field that this route does not accept.",
    "TENANT_CLAIM_MISSING": "Your identity does not carry exactly one tenant membership.",
    "TENANT_CLAIM_AMBIGUOUS": "Your identity does not carry exactly one tenant membership.",
    "TENANT_UNKNOWN": "Your tenant is not available.",
    "TENANT_DISABLED": "Your tenant is not available.",
    "TENANT_REGISTRY_UNAVAILABLE": "The service is temporarily unavailable.",
    "RETRIEVAL_SCOPE_INVALID": "The request could not be authorised.",
    "RETRIEVAL_UNAVAILABLE": "The service is temporarily unavailable.",
    "OWNERSHIP_MISMATCH": "The response was withheld.",
    "OWNERSHIP_LOOKUP_FAILED": "The service is temporarily unavailable.",
    "INGESTION_ATTRIBUTION_CONFLICT": "The document could not be accepted and has been quarantined.",
    "DOCUMENT_NOT_FOUND_FOR_TENANT": "Document not found.",
    "AUDIT_WRITE_FAILED": "The service is temporarily unavailable.",
    "MODEL_INVOCATION_FAILED": "The answer could not be generated.",
    "INTERNAL_ERROR": "The request failed.",
}


class Denied(Exception):
    """A fail-closed refusal. `detail` is for the audit record's diagnostics and is never returned to the caller."""

    def __init__(self, reason, detail=""):
        super().__init__(f"{reason.code}: {detail}")
        self.reason = reason
        self.detail = detail
