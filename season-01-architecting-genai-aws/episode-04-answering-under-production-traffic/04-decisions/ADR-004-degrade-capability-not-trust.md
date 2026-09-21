# ADR-004 — Degrade capability, not trust

**Status:** **ACCEPTED in direction** (2026-09-20). Carries a recorded decision and a recorded decision.

**the product owner (2026-09-20):** ACCEPTED as an **architectural invariant**. No degradation rung, operational switch, failure mode or overload condition may bypass eligibility, authorisation, currency, the four-state answerability rule or required citation behaviour. **Operators may reduce service; operators may not reduce trust**.

## Context
Under pressure, systems are tempted to buy availability by skipping work. In this system the skippable-looking work is
exactly what Episodes 02 and 03 established: per-request eligibility from current grants, and a currency check against
authority. a recorded decision rules retrieval-only degraded answers out and states the principle:

> **Episodes 02 + 03 determine whether an answer is allowed. Episode 04 determines whether the system has capacity to
> attempt that work now. Lack of capacity must never turn an otherwise unanswerable request into an answerable one.**

## Decision question
DQ-D: what may degrade, and what may never degrade?

## Options considered
1. Retrieval-only responses under load (sources without generation).
2. Reuse of recent answers across users or across a currency boundary.
3. **An ordered degradation ladder of capability-only steps, with a fixed, enforced list of properties that never
   degrade.**
4. No degradation at all: answer fully or refuse.

## Proposed decision
Option 3.

**May degrade (capability):** breadth of retrieval; optional re-ranking or enrichment; answer length and generation
budget; optional follow-up suggestions; concurrency admitted; the buffer's size; non-essential background work. Each
step is named, ordered and applied with hysteresis (ADR-008), and the response states what was reduced (FUN-003).

**Never degrades (trust) — enforced, not documented:**
- request-time eligibility from current grants (SEC-001);
- the request-time currency check against authority, and the withhold behaviour when it cannot be completed (FRS-C-003);
- the four-state rule: only *known current* is served;
- citation of what the answer used;
- the refusal vocabulary itself.

**Ruled out:** retrieval-only answers — retrieval alone establishes neither eligibility nor currency — and
any cross-user or cross-currency reuse of results (DATA-001).

**Enforcement:** the trust checks sit on the single path every answer takes, so no degradation step *can* bypass them;
the ladder controls only what happens before and after that path. FX-3 deliberately breaks this and must fail.

## Why
- Availability bought by weakening trust destroys the value of the previous two engagements, and would be invisible to
  the user at exactly the moment they are most rushed.
- A fixed ladder is testable; ad-hoc degradation during an incident is not (RSK-06).
- Capability reduction is honest: the user is told what they did not get.

## Trade-offs
- Less headroom than a design that may drop checks: the trust work is a fixed cost per request.
- The ladder must be maintained as features are added; a new optional feature is a new rung.
- "Degraded" needs explaining to users, or it reads as brokenness.

## Rejected alternatives
- **Retrieval-only (ruled out by a recorded decision).**
- **Answer reuse across users:** breaks per-request eligibility; a cache keyed by content is a derived copy with the
  same obligations (DATA-001).
- **No degradation:** wastes an opportunity to serve useful, slightly smaller answers during a burst.

## Consequences
- The cost floor per admitted request is set by the trust checks; capacity planning starts from there.
- Every degradation step needs a test that the invariants still hold while it is active (VT-6).
- "Degrade capability, not trust" becomes the episode's central teaching line.

## Validation required
VT-6 (invariants hold during shedding, degradation and recovery), VT-2 (the ladder behaves as stated), VT-4 (withhold
when currency cannot be confirmed). **FX-3** breaks this deliberately and must be caught.

## What would cause us to revisit
- A trust check becomes provably cheap enough to change the capacity model (it would still not become optional).
- The product introduces a genuinely non-authoritative mode with its own explicit contract, which would be a new
  product decision, not a degradation step.
