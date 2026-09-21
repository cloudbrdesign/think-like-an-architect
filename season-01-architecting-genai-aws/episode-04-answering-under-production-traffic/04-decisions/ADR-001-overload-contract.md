# ADR-001 — The overload contract: a stated promise and an explicit refusal

**Status:** **ACCEPTED in direction** (2026-09-20).

**the product owner (2026-09-20):** ACCEPTED. Do not prematurely freeze a universal p95 number. E3 defines the measurable lab objective and explains how concurrency, latency and throughput relate. The architecture owns the promise; the lab demonstrates it with deliberately small values.

## Context
The incident had no contract. Under saturation the outcome was decided by timeouts, platform throttling and client
retries. Nobody could say what the assistant promised, so nobody could tell whether it was behaving correctly.
a recorded decision rules that a caller-visible overload contract is a MUST.

## Decision question
DQ-A: what does the assistant promise, to whom, at what demand — and what does a caller receive when that promise
cannot be met?

## Options considered
1. A latency objective for all requests, with no stated capacity.
2. **A stated capacity expressed as admitted concurrency, with a tail-latency promise for admitted requests, and a typed
   refusal beyond it.**
3. Tiered promises per request class from the start.
4. No published promise; best effort with monitoring.

## Proposed decision
Option 2. The system publishes:
- an **admitted capacity** expressed primarily as concurrent in-flight answers (ASM-005: duration, not arrival rate, is
  what exhausts this system), with the equivalent request rate stated for planning;
- a **promise** for admitted requests, stated at the tail (p95) and measured by a recorded method (OPS-004);
- three possible outcomes, always explicit: **answer**, **degraded answer** (ADR-004), **refusal**;
- a refusal that is **typed** — capacity, not failure and not "unanswerable" — and carries retry guidance (ADR-006).

Tiering (option 3) is deliberately deferred: one promise is teachable and testable, and the fair-share mechanism
(ADR-003) already prevents the worst unfairness.

## Why
- An unstated promise cannot be held, tested, operated or explained; every later decision needs this contract to exist.
- Concurrency is the honest unit for this workload; a request-rate-only promise would mislead when answer duration moves.
- A typed refusal is what makes correct client behaviour possible at all (ADR-006), and it distinguishes "we are busy"
  from "this cannot be answered", which Episodes 02 and 03 already make a meaningful distinction.

## Trade-offs
- A published number invites comparison and constrains rollout plans.
- A p95 promise tolerates a slow tail by design; some users will see worse than the promise.
- Concurrency is less intuitive to non-engineers than "requests per second" and needs explanation (TP-1, TP-2).

## Rejected alternatives
- **Latency objective only:** cannot be enforced at admission; it becomes a wish.
- **No published promise:** the status quo that produced the incident.
- **Tiering now:** more machinery than the evidence justifies; revisit if measurement shows classes with genuinely
  different costs.

## Consequences
- Capacity and headroom become operational facts with an owner (OPS-001, CMP-002).
- Every mechanism downstream of admission must preserve the outcome vocabulary.
- The capacity number must be re-measured whenever answer duration or downstream quotas change.

## Validation required
VT-1 (promise holds at stated capacity, measured method recorded) and VT-2 (beyond capacity the stated rule is what
happens). FX-1 shows what the absence of this contract looks like.

## What would cause us to revisit
- Measurement shows answer duration varies so widely that a single concurrency number is meaningless.
- A class of requests appears whose cost differs by an order of magnitude (then reconsider tiering).
- The product decides that refusal is unacceptable for some population, which would reopen Option 5 of the analysis.
