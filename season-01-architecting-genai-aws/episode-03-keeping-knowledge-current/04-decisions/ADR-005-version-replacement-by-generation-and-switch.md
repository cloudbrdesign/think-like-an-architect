# ADR-005 — Version replacement by generation and switch

**Status:** accepted (2026-09-16) · **Answers:** DQ-D · **Options:** Option 4's mechanism at document scope

## Context
FRS-003 forbids answers that mix sections from two versions of a document. SEC-001 forbids any transient widening of
eligibility, which an in-place update can cause if content becomes retrievable before its classification is written, or
if a document's section boundaries change between versions.

## Decision
1. **A document's derived content is written as a complete generation**, identified by the authoritative version it was
   built from. Content and its classification are written together; nothing in a generation is retrievable until the
   whole generation is complete.
2. **Switching is atomic per document:** the request path sees either the old generation or the new one, never a mixture.
3. **The previous generation is removed after the switch,** so only one generation of a document is retrievable at a
   time.
4. **Section boundaries belong to the generation**, so a new version's sections never inherit the previous version's
   labels or offsets.
5. **A failed build leaves the previous generation serving** and the document in the pending set (ADR-002), rather than
   leaving a partial state.

## Alternatives considered
| Alternative | Why not |
|---|---|
| In-place chunk update | Mixed-version windows (RSK-04) and transient label/content mismatch (RSK-06) |
| Delete all chunks, then re-add | Guarantees an availability hole and a window where the document silently does not exist |
| Whole-index generations (Option 4) | Correct but far too slow and costly for the 4-hour window (ASM-008, CON-007) |
| Keep both versions and filter at query time | Doubles the index, and makes safety depend on filter correctness rather than on what exists |

## Consequences
- **Good:** no mixed-version answers; no partial visibility; failures are clean.
- **Cost:** transient duplicate storage per document during a switch, and a switch mechanism the retrieval store must
  support — a capability to confirm at implementation design.
- **Follow-on:** ADR-006 (removal of the old generation is part of the deletion surface), ADR-008 (rebuild reuses the
  same mechanism at partition scope).
