"""Deletion as a derived-state obligation (CTL-034; ADR-006).

    DELETION IS NOT AN INDEX OPERATION. IT IS AN OBLIGATION ACROSS EVERY DERIVED COPY THAT ACTUALLY EXISTS.

Two phases, deliberately distinguished in the evidence:

    LOGICAL   from the next request the content is not served — the authoritative record says DELETED, and the
              request-time check discards it (ADR-002). Immediate, but nothing has been removed yet.
    PHYSICAL  the derived copies are removed, within the obligation window.

The derived-copy graph below is THIS implementation's, discovered from what it builds — not an illustrative list and
not padded to look thorough. If a later design adds a derived copy, it is added here and the ledger proves it too.
Backups are governed by retention expiry: the ledger records that a retained backup still contains the
record and when it expires; restore-and-redelete is not the normal mechanism.
"""
from dataclasses import dataclass

# The derived copies this implementation actually creates.
SECTION_OBJECT = "section_object"              # S3 object per section per generation
KNOWLEDGE_BASE_DOCUMENT = "knowledge_base_document"   # custom document in the tier's knowledge base
VECTOR_ENTRY = "vector_entry"                  # vectors written by the knowledge base for that document
GENERATION_RECORD = "generation_record"        # the generation item in the convergence store
PENDING_ENTRY = "pending_entry"                # the pending item, if one is open
DERIVED_COPIES = (SECTION_OBJECT, KNOWLEDGE_BASE_DOCUMENT, VECTOR_ENTRY, GENERATION_RECORD, PENDING_ENTRY)

LOGICAL, PHYSICAL = "LOGICAL", "PHYSICAL"
PENDING, DONE, FAILED = "PENDING", "DONE", "FAILED"


@dataclass(frozen=True)
class Obligation:
    """One document's deletion obligation, as recorded in the content-free ledger."""
    document_id: str
    record_version: int
    authoritative_deletion_at: str
    logical_at: object = None
    copies: tuple = ()                 # ((kind, status, detail), …)

    @property
    def physical_complete(self):
        """Every derived copy in the graph must be proven removed — not merely the ones the caller mentioned.

        A partial entry stays in the LOGICAL phase: content is no longer served, and the obligation is still open.
        """
        proven = {kind for kind, status, _ in self.copies if status == DONE}
        return proven == set(DERIVED_COPIES)

    def item(self):
        return {"document_id": self.document_id, "record_version": self.record_version,
                "authoritative_deletion_at": self.authoritative_deletion_at, "logical_at": self.logical_at,
                "phase": PHYSICAL if self.physical_complete else LOGICAL,
                "copies": [{"kind": k, "status": s, "detail": d} for k, s, d in self.copies]}


def ledger_entry(document_id, record_version, authoritative_deletion_at, logical_at, results):
    """`results` is {derived copy kind: (status, content-free detail)}. Unknown kinds are refused, not ignored."""
    unknown = sorted(set(results) - set(DERIVED_COPIES))
    if unknown:
        raise ValueError(f"not part of this implementation's derived-copy graph: {unknown}")
    copies = tuple((kind, results[kind][0], results[kind][1]) for kind in DERIVED_COPIES if kind in results)
    return Obligation(document_id, record_version, authoritative_deletion_at, logical_at, copies).item()


def outstanding(entry):
    """Which derived copies a ledger entry does not yet prove removed (drives VT-6 and the FX-4 theme)."""
    proven = {c["kind"] for c in entry.get("copies", []) if c["status"] == DONE}
    return sorted(set(DERIVED_COPIES) - proven)
