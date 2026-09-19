# ADR-001 — Authoritative state model for change

**Status:** accepted (2026-09-16) · **Answers:** DQ-A · **Options:** [ARCHITECTURE_OPTIONS_ANALYSIS.md](ARCHITECTURE_OPTIONS_ANALYSIS.md)

## Context
Incident 1 happened because the assistant's idea of a document was content plus classification plus version. The record
also carries a **status** (in force, superseded, withdrawn, deleted), an **effective-from time** and, for supersession, a
**pointer to the replacing document** — and none of those were inputs to answering. Text inside documents also claims
supersession, and must never be believed (SEC-004, RSK-11).

## Decision
The authoritative record for a document (and its marked sections) is defined as: identifier · content version ·
**status** · **effective-from time** · **supersession pointer** · classification label and scope · retention class.

1. **Status, effective time and supersession are answering inputs**, alongside the Episode 02 label, scope and version.
2. **The index never holds authority.** It may carry a copy of these fields as a hint for filtering, but a hint is never
   the basis for treating content as current.
3. **Supersession by another document** is distinct from a new version of the same document. Both make the old content
   not current; they differ in what replaces it.
4. **Content is never a source of status.** Only the records system changes status.
5. **Granularity:** changes apply at document level, and at section level where the records system marks sections; a
   section inherits its document's status.
6. **Authoritative versus derived, explicitly:** the records system is authoritative. The retrieval index is derived
   state. The pending and convergence state of ADR-002 and ADR-003 is *also* derived operational state. Neither becomes a
   second source of truth.
7. **Authority wins on disagreement.** Where derived state and the authoritative record differ, the record decides and the
   derived state is repaired. Where the system cannot establish enough authoritative state to satisfy the approved safety
   policy, it follows the approved fail-closed behaviour rather than trusting derived state.

## Alternatives considered
| Alternative | Why not |
|---|---|
| Keep Episode 02's fields only (content, label, scope, version) | Reproduces incident 1: supersession is invisible |
| Resolve status only at indexing time | Makes safety a function of pipeline latency, which the decision separates from FRS-002 |
| Infer supersession from document text or naming conventions | Untrusted input; fails SEC-004 |
| Model validity as effective-date ranges on content only | Cannot express withdrawal without replacement, or deletion |

## Consequences
- **Good:** one vocabulary for every later decision; supersession becomes mechanical; FRS-002 can be stated in terms of
  authoritative facts rather than index timing.
- **Cost:** the records system must expose status, effective time and supersession (ASM-005); if it cannot, this ADR is
  the first thing to revisit.
- **Follow-on:** ADR-002 (how these facts affect serving), ADR-003 (how changes to them are learned).
