# ADR-003 — Partitioned capacity: floors for answering and change processing, fair share within answering

**Status:** **ACCEPTED in direction** (2026-09-20).

**the product owner (2026-09-20):** ACCEPTED. Fairness key for this scenario is the depot, documented as a configurable **fairness domain**: one domain must not consume the capacity needed by all others.

## Context
Answering and Episode 03's change processing draw on the same finite capacity, including the records system that serves
request-time currency checks (ASM-007). In the incident they collided. a recorded decision rules that both workloads get floors,
that neither may be starved indefinitely, that overload in either must not consume all shared capacity, and that falling
freshness must be observable.

## Decision question
DQ-F (how the two workloads share one system) and DQ-C's fairness question (LOD-008).

## Options considered
1. Strict priority to answering, background work best-effort.
2. Strict priority to change processing during bulletins.
3. **Partitioned capacity: a reserved floor for each workload, a shared elastic pool, and fair share across depots
   within answering.**
4. One shared pool with no partitioning (the status quo).

## Proposed decision
Option 3.
- **Floors:** answering and change processing each hold a reserved minimum share of capacity — including downstream
  permits — that the other cannot consume.
- **Elastic middle:** capacity above the floors is shared and may be borrowed in either direction, and is reclaimed when
  the owner needs it.
- **Fair share within answering:** each depot (or client class) receives a share of the answering pool, so no single
  population can consume it all.
- **Visible degradation:** when change processing is held to its floor, the Episode 03 watermark stalls, lag is reported
  and the breach alerts (FRS-C-002). Slowing freshness is never silent.
- **Currency contract unchanged:** whatever the allocation, what may be *served* is still governed by Episodes 02 and 03.

## Why
- Only partitioning satisfies B5 by construction; every priority scheme eventually starves the loser.
- The bulletin case is the proof: the event that creates the question load is the same event that creates the change
  load, so neither may be allowed to win completely.
- Fair share is what makes "whose request is refused" an architectural answer instead of an accident of arrival order.

## Trade-offs
- Reserved capacity is idle when its owner is quiet: real cost (CON-006).
- More knobs to set, review and explain (CON-004).
- Borrowing re-introduces coupling; the reclaim path must be prompt or the floors are theatre.

## Rejected alternatives
- **Strict priority to answering:** ruled out by a recorded decision; it also silently degrades the Episode 03 claim.
- **Strict priority to change processing:** starves answering at exactly the moment staff need it (FX-4).
- **No partitioning:** the incident.

## Consequences
- Allocation numbers become a reviewed operational artefact, measured at the validation gate, not asserted.
- Freshness lag becomes a first-class capacity signal alongside queue age (ADR-007).
- The floors bound how much of the downstream budget either workload can consume (ADR-005).

## Validation required
VT-5 (both floors hold under a bulletin burst; freshness degrades visibly), VT-2 (fairness across depots), VT-7 (the
stall is observable). FX-4 remains the candidate experiment for starvation.

## What would cause us to revisit
- Measurement shows change processing can be deferred out of peaks without breaching a freshness window, which would
  simplify the allocation.
- The records system gains independent capacity for currency checks, removing the contention (ASM-007 false).
- Fair share proves unnecessary because depot traffic is naturally balanced.
