# ADR-008 — Repair and rebuild

**Status:** accepted (2026-09-16) · **Answers:** DQ-H · **Options:** Option 4's mechanism, used as the exceptional path

## Context
Drift will happen: missed notifications, failed batches, poison documents, defects in change processing. Kestrelmoor's
current answer is a full re-index that takes days (ASM-008), competes with answering (CON-004) and hides defects
(RSK-10). NFR-002 requires that a rebuild neither stops answering nor widens eligibility.

## Decision
1. **Reconciliation-driven targeted repair is the normal mechanism.** Each difference reconciliation finds becomes a
   scoped repair for one document, applied through the same ordered, idempotent path as any change (ADR-004, ADR-005).
2. **Operators can reprocess** a document, a set or a partition on demand, with a recorded reason (OPS-002); the same
   path, not a special one.
3. **Full rebuild is exceptional** and runs as a parallel generation: build, verify against the authoritative export,
   then switch per partition. The current index keeps answering throughout.
4. **A rebuilt generation is verified before it serves:** every document's version, status, label and scope must match
   the export, and the Episode 02 eligibility suite must pass against it (VT-10). An unverified generation never serves.
5. **Rebuild is not a repair strategy for defects:** if reconciliation drift recurs, the defect is fixed; a rebuild that
   is used to hide it is recorded as an incident.
6. **When incremental derived state is considered untrusted** — qualitative triggers, with thresholds measured during
   implementation rather than invented now:
   - reconciliation reports drift that targeted repair cannot close, or the same documents drift repeatedly;
   - the watermark for a class cannot be advanced because reconciliation cannot complete;
   - ordering or idempotency was violated by a defect, so the current state may reflect an older authoritative version;
   - a change-processing defect is found whose blast radius over past changes cannot be bounded;
   - a store is restored from backup, so its contents no longer correspond to any known watermark.
   Any of these makes the affected partition's derived state unprovable, which is the condition rebuild exists for.

## Alternatives considered
| Alternative | Why not |
|---|---|
| Periodic full rebuild as the routine mechanism | RSK-10, CON-004 and CON-007: slow, costly, hides defects, competes with answering |
| Repair by deleting and re-adding affected documents in place | Availability holes and transient states (ADR-005) |
| Manual scripts per incident | Not operable by six engineers; no evidence trail |
| Rebuild that swaps the whole index at once | A single atomic swap across tiers is harder to make safe than per-partition switches, and failure is all-or-nothing |

## Consequences
- **Good:** repair is routine, ordered and evidenced; rebuild exists without becoming the method.
- **Cost:** storage for a parallel generation during rebuild, and a verification step that must itself be trustworthy.
- **Security:** because the rebuild is verified against the authoritative export before serving, no rebuild path can
  widen eligibility (SEC-001).
