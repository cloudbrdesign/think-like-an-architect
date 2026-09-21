# ADR-006 — The retry contract: server-issued guidance, server-enforced budget, safe repetition

**Status:** **ACCEPTED in direction** (2026-09-20).

**the product owner (2026-09-20):** ACCEPTED. E3 must make retry amplification **directly demonstrable**.

## Context
At 07:05 the users retried. Every retry was a new request, and the queue grew faster than it drained. Retry
amplification turned a survivable burst into an outage (RSK-01). LOD-007 requires that retry behaviour is bounded by the
architecture, not by client goodwill; FUN-004 requires repetition to be safe.

## Decision question
DQ-E: how do clients retry without amplifying the overload?

## Options considered
1. Document a retry policy and rely on clients to implement it.
2. **Server-issued retry guidance, enforced by a server-side retry budget, with safe repetition and single-flight
   coalescing.**
3. Server-side queueing of retries on the caller's behalf.
4. No guidance; clients decide.

## Proposed decision
Option 2.
- Every capacity refusal carries **retry guidance**: a wait time, individually jittered so that refused callers do not
  return in a synchronised wave.
- A **retry budget** is enforced server-side per client population: retries beyond the budget are refused cheaply and
  counted, so ignoring the guidance cannot multiply load.
- **Safe repetition:** a repeated question carries a caller-supplied identity for the attempt, so a retry is recognised
  rather than duplicated, and never produces duplicate side effects or duplicate downstream cost.
- **Single flight:** identical in-flight questions from the same user are coalesced onto one execution.
- The first-party clients implement backoff with jitter and honour the guidance; the server does not depend on them
  doing so.

## Why
- Guidance without enforcement is a request, and under load a request is not a control (option 1 is what most systems
  do, and it fails).
- Jitter is the cheap mechanical fix for the synchronised second wave.
- Safe repetition is what makes retrying acceptable at all; without it, retry policy and correctness fight each other.

## Trade-offs
- Budgets and attempt identity add per-request state and a small cost on the cheapest path.
- A too-tight budget punishes honest clients on a flaky network.
- Coalescing must respect eligibility: two users asking the same question are not the same request (SEC-001).

## Rejected alternatives
- **Documented policy only:** unenforceable, and the incident's actual failure.
- **Server-side retry queue:** hides the overload and grows the backlog invisibly.
- **No guidance:** guarantees the amplification pattern.

## Consequences
- Refusals must be cheap (NFR-004), because under a retry storm refusal is the dominant workload.
- Retry-budget exhaustion becomes an observable signal distinct from saturation (ADR-007).
- Client libraries become part of the architecture's surface, and change with it (ASM-008).

## Validation required
VT-3 (bounded retries keep offered load bounded; repetition is safe and non-duplicating), VT-8 (no synchronised herd at
recovery). **FX-2** removes the budget, jitter and guidance and must reproduce amplification.

## What would cause us to revisit
- Clients stop being first-party (ASM-008 false), which would move all enforcement to the edge.
- Measurement shows coalescing yields little, and its complexity is not repaid.
