# ADR-005 — Bounded downstream permits with adaptive reduction

**Status:** **ACCEPTED in direction** (2026-09-20).

**the product owner (2026-09-20):** ACCEPTED. The adaptive mechanism protects against a capacity boundary the application does not fully control, and must not make the externally visible service contract inexplicable.

## Context
Our capacity ends where the platform's begins. The model service enforces its own quotas and rejects calls beyond them;
the records system has finite capacity shared with change processing (ASM-006, ASM-007). Episode 01 recorded this as
RR-13 and deferred the mitigation — "queueing and back-pressure; cells; capacity reviews" — to Episode 04.

## Decision question
DQ-B: how does the architecture bound the load it places downstream, and what does it do when refused?

## Options considered
1. Call downstream freely and handle rejections when they occur.
2. **A fixed permit budget per downstream dependency, partitioned by workload, reduced adaptively when the dependency
   signals distress.**
3. Fully adaptive limits with no fixed ceiling (analysis Option 4).
4. Retry downstream rejections aggressively to win capacity back.

## Proposed decision
Option 2.
- Each downstream dependency has a **permit budget**; no call proceeds without a permit. The sum of the partitions'
  permits never exceeds the budget (ADR-003).
- The budget is **reduced adaptively** on sustained downstream rejection or latency growth, and restored gradually.
- A downstream rejection is classified as **saturation**, not failure (LOD-010), and surfaces as a capacity outcome.
- Downstream calls are **not retried by default**; where a retry is genuinely safe and cheap it spends the same retry
  budget as the caller's (ADR-006).
- If the currency check cannot obtain a permit or a timely answer, the request is **withheld** per Episode 03 — never
  served unverified (ADR-004).

## Why
- A permit budget is the only way to guarantee we do not become the cause of our own downstream throttling.
- Adaptation belongs here, where the true limit is unknowable in advance, and not in the user-facing promise, which must
  stay explicable (ADR-001).
- Classifying saturation separately from failure is what lets every other component respond correctly.

## Trade-offs
- Permits add a coordination cost on every call.
- An adaptive reducer can overreact to a slow dependency; damping and floors are required.
- Leaving downstream rejections unretried can waste work that a single retry would have recovered.

## Rejected alternatives
- **Free calling:** guarantees quota exhaustion at exactly the worst moment (the incident, 07:07).
- **Fully adaptive, no ceiling:** unexplainable promise; no protection while the controller learns.
- **Aggressive downstream retry:** the amplification pattern, moved one layer down.

## Consequences
- Downstream rejection rate becomes a first-class signal (ADR-007).
- The permit budget must be re-derived whenever a quota or answer duration changes (currency check at each gate).
- The lab can demonstrate the whole behaviour by setting deliberately tiny permits (CON-007).

## Validation required
VT-4 (stay inside downstream limits; saturation recognised; withhold preserved), VT-2 (behaviour at the boundary),
VT-7 (the signal is visible).

## What would cause us to revisit
- Downstream quotas become elastic or per-request-priced, changing the nature of the bound.
- Measurement shows the records system, not the model service, is the binding constraint (likely, and it changes sizing
  but not the mechanism).
