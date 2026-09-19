# ADR-007 — Freshness measurement and evidence

**Status:** accepted (2026-09-16) · **Answers:** DQ-F

## Context
The decision records that processing latency is not provable freshness. Safety assurance and internal audit will ask when a
bulletin became effective in the assistant (RSK-09), and Episode 02's audit discipline requires content-free records.

## Decision
Freshness is reported at two levels, and both are evidence.

1. **Per answer:** the authoritative version confirmed at answer time — and, where an answer was withheld, the reason
   (pending change, superseded, withdrawn, deleted or unknown state). This is what a supervisor sees when questioning an
   answer or its absence.
2. **System-wide:** the convergence watermark (defined precisely below), the pending count, the age of the oldest pending
   change per class, failed changes, and the time of the last completed reconciliation.

3. **Windows are commitments per class** (FRS-001). A breach raises an alert naming the class and the affected
   identifiers, and is treated as an incident when the pending window is exceeded (NFR-003).
4. **Canary changes prove the measurement is not vacuous:** synthetic records are changed on a schedule, and the measured
   lag must track the injected delay. A measurement that cannot detect an injected delay is not evidence (VT-8).
5. **Reports** for safety assurance and audit are generated from these records, content-free (SEC-005, OPS-003).

### Watermark semantics (required)

| Question | Answer |
|---|---|
| **What does it assert?** | "For this change class, every authoritative change with an effective time at or before **T** has been either applied to derived state or is listed as pending." It is a statement about *completeness of knowledge*, not about processing progress |
| **What may advance it?** | Only a completed reconciliation pass over that class against the authoritative export. Advancing to T requires that the pass covered every record in the class and that each difference it found became a pending entry or a repair |
| **What stops a missed notification advancing it falsely?** | Notifications never advance the watermark. A change that was never delivered is invisible to delivery, so only the reconciliation comparison — which reads authority, not the notification stream — can move T |
| **How does reconciliation contribute?** | It is the sole source of advancement, and it also produces the missing, extra and divergent sets that become repairs (ADR-003) |
| **When reconciliation is overdue** | T stops moving; its age grows and becomes visible. Beyond the approved window the class enters conservative mode (ADR-002): safety-critical content is withheld rather than served on an unprovable claim |
| **How do pending items interact?** | The watermark and the pending set are complementary: T bounds what the system *knows about*; the pending set enumerates what it knows is *not yet applied*. Content in the pending set is never current, whatever T says |
| **What is the global floor?** | The conservative minimum across classes. Any statement about the system as a whole uses the floor, so a class that is behind can never be hidden by a class that is current |

**What the watermark is not:** the timestamp of the last event processed, the last successful job, the newest document
indexed or the emptiness of a queue. Those describe work observed; the watermark describes work accounted for. The
architecture claims only the strongest statement its evidence supports.

**The evidence must answer:** what authoritative state have we proven applied · what remains pending · how old is the
oldest pending change · when did reconciliation last establish completeness · are we inside the approved window · what
claim can the system make about freshness right now.

## Alternatives considered
| Alternative | Why not |
|---|---|
| Pipeline latency and queue depth as the freshness metric | Measures the work seen, not the work missed; it is exactly what Kestrelmoor has today. Queue depth, event age and last-successful-job time remain useful **operational** metrics, and none of them is freshness evidence |
| Per-document "last indexed" timestamps only | Says when something was processed, never whether anything is outstanding |
| Freshness attested by the ingestion service's own success rate | Success of the observed work says nothing about completeness |
| No canaries | The measurement could read healthy while broken, which is the vacuity Season 1 tests for |

## Consequences
- **Good:** "what did the system know, and when?" is answerable; FX-3's damage becomes visible in the evidence.
- **Cost:** canary records and their exclusions must be designed so they never pollute answers or evidence.
- **Follow-on:** ADR-008 (what the platform does when the evidence says the system is behind).
