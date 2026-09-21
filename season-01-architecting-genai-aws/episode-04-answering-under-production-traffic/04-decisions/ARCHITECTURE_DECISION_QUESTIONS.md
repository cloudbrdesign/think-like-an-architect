# Architecture Decision Questions — Kestrelmoor Knowledge Assistant: answering under production traffic

**Status:** **APPROVED as the question set** (2026-09-20); the definition is frozen. Answers are developed at
the architecture options and ADR gate.

**Ruled at approval:** a retrieval-only degraded answer is **ruled out** as a DQ-D candidate. Under pressure
the architecture may degrade capability — never trust. See ADR-004.

These are the questions the architecture must answer. **Try to answer each one yourself.** At this gate they are
questions only: the options analysis and the architecture decision records follow at the next gate, after the definition
is approved. Candidate approaches are listed so the questions are concrete, **not** as a shortlist with a hidden winner.

---

## DQ-A — What does the assistant promise, to whom, and at what demand?

**Decision question:** What is the stated promise for an admitted request, at what capacity does it hold, and how is it
measured?

**Questions to resolve**
- Is the promise a latency target at a percentile, a completion guarantee, or both? Which percentile, and why that one?
- Is capacity stated as a request rate, a concurrency, or both — and which one actually binds here (ASM-005)?
- Is there one promise for everyone, or different promises for different request kinds (a bulletin question at shift
  start versus a background report)?
- What headroom is kept, and who may consume it?
- How is the capacity number produced, and how is it re-measured when the system changes (OPS-004)?

**Candidate approaches to evaluate:** a single latency objective for all requests · tiered promises by request class ·
capacity expressed as admitted concurrency · capacity expressed as rate with a concurrency cap · scheduled capacity
(higher admitted capacity at known shift starts).

**Driven by:** BUS-001, BUS-003, BUS-004, LOD-003, NFR-001, OPS-004 · RSK-08

---

## DQ-B — Where is the boundary between our capacity and the platform's?

**Decision question:** How does the architecture bound the load it places on the model service and the records system,
and what does it do when they refuse (ASM-006, ASM-007)?

**Questions to resolve**
- What limits concurrent downstream calls: a fixed ceiling, a dynamic limit that reacts to throttling, or a token/permit
  scheme?
- Are downstream refusals retried, and if so under what budget (LOD-006, LOD-007)?
- Should the system reserve part of downstream capacity for the currency checks that Episode 03 requires on every
  request, and part for change processing?
- What is the correct response when the currency check itself cannot be completed in time (FRS-C-003)?
- How does the architecture avoid mistaking a downstream quota refusal for a downstream failure (LOD-010, RSK-05)?

**Candidate approaches to evaluate:** static concurrency limits per downstream · adaptive limits driven by observed
latency or rejection · permits split by workload class · circuit breaking on sustained refusal · reserved capacity pools.

**Driven by:** LOD-006, LOD-010, FRS-C-003, CON-002 · Episode 01 RR-13 · RSK-05

---

## DQ-C — What happens to demand beyond capacity: queue, shed, or both?

**Decision question:** What is the stated rule for excess demand, and how is it kept from becoming an unbounded wait
(LOD-004, LOD-005)?

**Questions to resolve**
- Is there a queue at all? If so, what bounds it: length, age, or an admission decision made before entry?
- When a queued request can no longer meet the promise, is it discarded before execution, and who is told?
- Which requests are shed first, and on what basis — arrival order, depot, request class, user, or cost to serve?
- How is fairness defined so one depot or workload cannot consume everything (LOD-008, TP-17)?
- How cheap must a refusal be, and what is the refusal deadline (LOD-002, NFR-004)?
- What may an operator change during an incident, and what must they never be able to switch off (OPS-003)?

**Candidate approaches to evaluate:** admission control with no queue · bounded-age queue with pre-execution expiry ·
per-class queues with weighted service · fair-share quotas per depot or user · cost-aware shedding (shed the most
expensive requests first) · load shedding driven by measured saturation rather than a fixed threshold.

**Driven by:** LOD-002, LOD-004, LOD-005, LOD-008, NFR-002, NFR-004, DATA-002, OPS-003 · RSK-03, RSK-04

---

## DQ-D — What may degrade, and what may never degrade?

**Decision question:** What is the ordered degradation ladder, and how is it constrained by the Episode 02 and Episode 03
invariants (LOD-001, LOD-009, SEC-001)?

**Questions to resolve**
- Which parts of an answer are optional: breadth of retrieval, re-ranking, answer length, citations' richness, follow-up
  suggestions?
- Is a retrieval-only response (sources without generated prose) an acceptable degraded answer, or a different product?
- Can any cached or precomputed artefact be reused safely, given that eligibility is per user and currency is per
  request (DATA-001)?
- How does the caller learn what was reduced (FUN-003), without leaking anything about restricted content (SEC-002)?
- What is the explicit list of things that never degrade — and how is that list enforced rather than merely documented?

**Candidate approaches to evaluate:** a fixed ladder with named steps · load-triggered steps with hysteresis ·
per-request-class degradation · retrieval-only mode · shorter generation budgets · no degradation at all (shed instead).

**Driven by:** LOD-001, LOD-009, FUN-001, FUN-003, SEC-001, SEC-002, DATA-001, CMP-001 · RSK-02, RSK-06

---

## DQ-E — How do clients retry without amplifying the overload?

**Decision question:** What retry contract binds the clients, and how is it enforced rather than requested
(LOD-007, FUN-002, FUN-004)?

**Questions to resolve**
- What does a capacity refusal carry: a retry-after time, a budget, a token, a position?
- Is the retry budget enforced at the client, at the edge, or both — and what happens when a client ignores it?
- How are retries made safe and non-duplicating (FUN-004): idempotency keys, request de-duplication, or single-flight?
- Should the user interface show progress or a queue position, and does that change retry behaviour?
- How is a retry distinguished from a genuinely new question by the same user?

**Candidate approaches to evaluate:** retry-after with mandatory client honouring · server-enforced retry budgets ·
exponential backoff with jitter in a shared client library · request coalescing for identical questions · single-flight
per user · a client-side circuit breaker.

**Driven by:** FUN-002, FUN-004, LOD-007, BUS-001 · RSK-01, TP-12, TP-13

---

## DQ-F — How do answering and freshness share one finite system?

**Decision question:** How are answering and Episode 03's change processing scheduled against each other, and how is the
trade-off made visible (FRS-C-001, FRS-C-002)?

**Questions to resolve**
- Does answering always win, does change processing have a floor, or does priority depend on the change class (a safety
  bulletin versus a routine reclassification)?
- Where do the two workloads actually contend: the records system, the index, the embedding or model service, or the
  compute that runs both?
- When change processing is slowed, how does the Episode 03 freshness position degrade **visibly** — stalled watermark,
  reported lag, alert — rather than silently?
- Can change processing be deferred out of a peak without breaking a freshness window, and who decides?
- Does a bulletin burst deserve *more* freshness priority precisely because it is also driving the question traffic
  (BUS-002)?

**Candidate approaches to evaluate:** strict priority to answering with a reserved floor for change processing ·
class-aware scheduling by change class · shifting non-urgent change work away from known peaks · isolating the two
workloads onto separate capacity · admission control applied to change processing as well as to answering.

**Driven by:** BUS-002, FRS-C-001, FRS-C-002, FRS-C-003, ASM-007 · RSK-04

---

## DQ-G — How is saturation seen, distinguished and alerted before users feel it?

**Decision question:** Which signals define saturation, and how do they separate "too busy" from "broken" and from "not
current" (LOD-010, OPS-001, OPS-002)?

**Questions to resolve**
- Which signals lead: queue age, concurrency utilisation, downstream rejection rate, latency percentiles, shed rate?
- What is the difference, in signals, between our own saturation and a downstream quota exhaustion?
- How is a stalled freshness watermark surfaced alongside capacity alerts, without conflating the two?
- What does an operator see first, and what single view would have shortened the incident above?
- What evidence is kept afterwards, and for how long, so a capacity claim can be reviewed (OPS-004, CMP-002)?

**Candidate approaches to evaluate:** queue-age-led saturation signal · utilisation-based signal · error-budget
approach · synthetic probes at known intervals · per-class dashboards · alerting on rate of change rather than level.

**Driven by:** LOD-010, OPS-001, OPS-002, OPS-004, CMP-002, BUS-004 · RSK-05, RSK-08

---

## DQ-H — How does the system recover, and how is recovery kept shorter than the incident?

**Decision question:** What happens as demand falls: how is the backlog handled, and how are cold caches, synchronised
retries and deferred change work prevented from re-creating the spike (NFR-003, RSK-07)?

**Questions to resolve**
- Is the backlog drained, discarded, or partly both — and what is the user told about requests that were waiting?
- How is a thundering herd avoided when many clients are told to retry at once (TP-13, TP-18)?
- How is the deferred change-processing work caught up without starving the answering that has just returned?
- What defines "recovered", who declares it, and how is the bounded recovery time measured (NFR-003)?
- Does the system return to full function in one step, or unwind the degradation ladder in stages with hysteresis?

**Candidate approaches to evaluate:** discard-then-restart · staged admission ramp · staggered retry-after values ·
warm-up of caches before full admission · hysteresis on every degradation step · explicit recovery state with its own
alert.

**Driven by:** NFR-003, LOD-005, FRS-C-001, OPS-002 · RSK-07, TP-18
