# ADR-003 — Change detection and completeness

**Status:** accepted (2026-09-16) · **Answers:** DQ-B · **Options:** Option 3, with Option 4's export as reference data

## Context
Notifications from the records system are at least once, may be duplicated, may arrive out of order and may be missed
(ASM-003). Incident 2 was a silent loss. The decision records the principle: *event delivery tells us about the
changes we received; reconciliation must help us discover the changes we did not.*

## Decision
Change detection has two independent mechanisms, and only one of them establishes completeness.

1. **Notifications provide low-latency change signals.** Each notification immediately records a pending entry (ADR-002)
   — so a received change becomes visible to the safety mechanism *before* expensive content processing completes — and
   queues the content work. Notifications are never treated as proof that the set of changes is complete.
2. **Reconciliation establishes completeness.** On a schedule, the system compares the authoritative export against the
   index's per-document state (identifier, version, status, label, scope) and produces three sets: missing, extra and
   divergent. Each difference becomes a repair.
3. **The watermark advances only through reconciliation.** "All changes effective before T are applied" is a statement
   reconciliation earns, never one notification delivery implies.
4. **Cadence by consequence (a policy shape, not a number):** more frequent reconciliation for
   safety-critical state and recently changed documents; a longer complete cycle for the full corpus. Numeric cadences are
   **measured during implementation** against document volume, change volume, burst behaviour, authority capacity,
   processing capacity and the approved freshness windows — never invented at this gate.
5. **Overdue reconciliation stalls the watermark**, which puts the safety class into conservative mode rather than
   silently continuing.

## Alternatives considered
| Alternative | Why not |
|---|---|
| Notifications only | Cannot detect what was never delivered; fails FRS-004 (incident 2) |
| Full comparison only, no notifications | Completeness without timeliness: the supersede and upward-reclassification semantics cannot wait for a cycle |
| Trust a delivery guarantee from the eventual messaging technology | The decision forbids assuming reliability from a later service choice; the records system's own outages can still drop changes |
| Reconcile only when an incident is suspected | Loss is silent by definition; there is nothing to suspect |

**The two mechanisms are complementary, and neither replaces the other:** delivery tells us about changes we received;
reconciliation tells us about changes we were never told about.

## Consequences
- **Good:** FRS-004 is satisfied by construction, and FX-3 (reconciliation disabled while notifications are dropped) has
  something real to break.
- **Cost:** the export must be obtainable at a useful cadence, and reconciliation cost grows with the corpus; it is
  partitioned and scheduled to stay affordable (CON-007).
- **Follow-on:** ADR-004 (how a discovered change is applied safely), ADR-007 (what the watermark proves), ADR-008
  (repair).
