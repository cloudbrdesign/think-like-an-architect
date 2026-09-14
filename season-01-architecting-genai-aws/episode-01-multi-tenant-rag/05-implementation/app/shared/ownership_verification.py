"""Detective control. It is not the tenant isolation control; see retrieval_scope.py.

DEFENCE IN DEPTH (CTL-017; ADR-005). After retrieval and before anything reaches the model, every retrieved chunk is
checked against the trusted ownership source:
  - its owning_tenant attribute must equal the context tenant;
  - its DOC# ownership record must exist and name the same owner.
If ANY chunk fails either check, the WHOLE request fails with OWNERSHIP_MISMATCH. Nothing is partially answered.
A chunk whose record is correctly owned but not AVAILABLE (for example DELETING) is discarded, not treated as a leak.

In the normal system this control should never fire: retrieval_scope.py already prevents other tenants' chunks from
being retrieved. It exists to detect a broken constraint or a broken attribution — and the sensitivity test proves it
does exactly that.
"""
from dataclasses import dataclass

from shared.ownership import AVAILABLE
from shared.reason_codes import OWNERSHIP_LOOKUP_FAILED, OWNERSHIP_MISMATCH, Denied
from shared.registry import RegistryUnavailable


@dataclass(frozen=True)
class VerifiedChunk:
    document_id: str
    title: str
    text: str


@dataclass(frozen=True)
class VerificationResult:
    outcome: str             # PASSED | DISCARDED | NOT_APPLICABLE
    verified: tuple          # VerifiedChunk, in retrieval order
    discarded_count: int


def verify(ctx, chunks, registry):
    if not chunks:
        return VerificationResult("NOT_APPLICABLE", (), 0)
    for chunk in chunks:
        if not chunk.document_id or chunk.owner_attribute != ctx.tenant_id:
            raise Denied(OWNERSHIP_MISMATCH, "retrieved chunk owner attribute does not match the tenant context")
    try:
        records = registry.get_documents(chunk.document_id for chunk in chunks)
    except RegistryUnavailable as error:
        raise Denied(OWNERSHIP_LOOKUP_FAILED, str(error)) from error
    verified, discarded = [], 0
    for chunk in chunks:
        record = records.get(chunk.document_id)
        if record is None or record.get("owner") != ctx.tenant_id:
            raise Denied(OWNERSHIP_MISMATCH, "ownership record missing or owned by another tenant")
        if record.get("status") != AVAILABLE:
            discarded += 1
            continue
        verified.append(VerifiedChunk(document_id=chunk.document_id, title=record.get("title", ""), text=chunk.text))
    return VerificationResult("PASSED" if discarded == 0 else "DISCARDED", tuple(verified), discarded)
