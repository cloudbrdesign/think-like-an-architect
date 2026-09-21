# ADR-008 — Bounded recovery: staged ramp, backlog by age, staggered return

**Status:** **ACCEPTED in direction** (2026-09-20).

**the product owner (2026-09-20):** ACCEPTED. Recovery is part of the architecture, not an operational afterthought.

## Context
In the incident, demand fell at 07:20 but service returned at 07:31: recovery outlasted the burst by eleven minutes
(RSK-07). A backlog of stale work, cold caches and a synchronised retry wave can re-create the spike that has just
ended. NFR-003 requires bounded, automatic recovery.

## Decision question
DQ-H: how does the system return to normal without re-creating the incident?

## Options considered
1. Lift all limits as soon as demand falls.
2. **Staged admission ramp with hysteresis, age-based backlog disposal and staggered retry guidance.**
3. Manual recovery under operator control.
4. Drain the entire backlog before admitting new work.

## Proposed decision
Option 2.
- **Backlog by age:** queued work that can no longer meet the promise is discarded before execution and its callers are
  told; only viable work is drained.
- **Staged ramp:** admitted capacity is restored in steps, with a settle period at each step, so the system re-enters
  service under control.
- **Hysteresis on every degradation rung:** capability is restored more slowly than it was removed, so the system does
  not oscillate at the boundary.
- **Staggered return:** retry guidance is spread across the refused population, so they do not all return at the same
  instant (ADR-006).
- **Freshness catch-up is scheduled, not unleashed:** deferred change processing resumes inside its floor and elastic
  share (ADR-003), never as an unbounded burst that starves the answering that has just come back.
- **Recovery is a named state** with its own signal and alert (ADR-007); "recovered" is defined by the promise holding
  at the stated capacity, not by the alert clearing.

## Why
- Most of the incident's second half was recovery, not overload: recovery deserves design, not hope.
- Discarding stale work is what makes the drain finite.
- A thundering herd is the predictable consequence of telling everyone to come back at the same time (TP-13, TP-18).

## Trade-offs
- A staged ramp means full capacity returns later than it technically could.
- Discarding backlog disappoints users who waited, even though the alternative is serving answers nobody is waiting for.
- Hysteresis makes behaviour at the boundary harder to reason about in a demo, and must be taught carefully.

## Rejected alternatives
- **Immediate full restoration:** re-creates the spike with a cold system.
- **Manual recovery:** fails NFR-003 and depends on a human being awake at 07:20.
- **Drain everything first:** spends the recovered capacity on abandoned work.

## Consequences
- Recovery time becomes a measured property with a target (NFR-003).
- The ramp and hysteresis parameters are measured at the validation gate, not asserted here.
- Operators get one explicit view of "where in recovery are we".

## Validation required
VT-8 (bounded, automatic recovery; no herd; backlog handled by age), VT-3 (staggered guidance holds), VT-5 (freshness
catch-up does not starve answering).

## What would cause us to revisit
- Measurement shows the backlog is always negligible, which would simplify the drain policy.
- Cold-start behaviour proves irrelevant at this scale, removing the need for a staged ramp.
