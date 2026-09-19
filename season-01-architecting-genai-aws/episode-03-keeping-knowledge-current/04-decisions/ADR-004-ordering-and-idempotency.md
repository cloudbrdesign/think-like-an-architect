# ADR-004 — Ordering and idempotency of change application

**Status:** accepted (2026-09-16) · **Answers:** DQ-B, DQ-G

## Context
FRS-005 is an invariant: late, duplicate or replayed changes must never reinstate an older version, classification,
status or a deleted document. Retries, replays and reconciliation repairs all deliver the same change more than once,
and notifications may arrive out of order (ASM-003).

## Decision
1. **The authoritative record's version and effective time are the ordering key** — never arrival time, never the
   pipeline's own sequence numbers.
2. **Application is monotonic per document:** a change is applied only if its authoritative version is newer than the
   version currently reflected. Older arrivals are recorded and discarded.
3. **Application is idempotent:** applying the same authoritative version twice produces the same state, so retries and
   reconciliation repairs are always safe.
4. **Deletion is terminal for the record's lifetime:** a deleted document cannot be reinstated by a late change; only a
   new authoritative record can bring content back.
5. **Reconciliation uses the same rule**, so a repair can never move a document backwards.

## Alternatives considered
| Alternative | Why not |
|---|---|
| Last write wins by arrival time | Exactly the FX-2 fault: a replayed older version wins |
| Strict ordered delivery from the transport | Assumes a guarantee the source does not offer |
| Global ordering across all documents | Unnecessary — ordering matters per document — and it would serialise bursts |
| Compare content hashes instead of versions | Cannot distinguish "unchanged content, new status" from "no change", and loses effective-time semantics |

## Consequences
- **Good:** replay safety becomes a property, not an operational hope; FX-2 has a precise thing to break.
- **Cost:** every derived record must carry the authoritative version it came from, and repairs must read it before
  writing.
- **Follow-on:** ADR-005 (how the write itself is made atomic).
