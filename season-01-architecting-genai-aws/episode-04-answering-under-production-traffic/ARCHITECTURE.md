# The architecture

## The situation

A knowledge assistant serves depots across a distribution network. It answers questions about procedures, and it keeps
its own index current as those procedures change. It works.

Then a Monday arrives where one depot posts a bulletin, every driver asks about it at once, and the assistant becomes
slow for everybody — including the depots that had nothing to do with it. Retries pile in. The freshness work that
keeps answers correct stops getting capacity. Some answers come back that should not have been answered at all.

Nothing was broken. Nothing was wrong in testing. There was simply more work than capacity, and **nobody had decided
what should happen in that case**, so the system decided by accident.

## The decision

> **Finite capacity requires an explicit service contract.**

Capacity is not a property you discover under load. It is a promise you make, and a promise implies deciding in
advance:

- what you will **refuse**, and how you will say so;
- **who** gets refused first, when not everyone can be served;
- what capability you will **drop** to stay useful;
- what you will **never** drop, however bad it gets.

The last one is the invariant:

> **Degrade capability, not trust.**
> *Operators may reduce service. Operators may not reduce trust.*

## The shape

Four elements, each earning its place:

| | Element | Why |
|---|---|---|
| 1 | **Partitioned capacity spine** | Each workload gets a bounded share and a protected floor, so answering cannot starve freshness and one tenant cannot starve the rest |
| 2 | **Direct admission inside partitions** | Decide at the door, immediately and cheaply. A request refused at admission costs almost nothing and tells the caller the truth at once |
| 3 | **A narrow, age-bounded burst buffer** | Absorb a *short, known* burst only. Bounded by capacity **and by age**, because work that has waited past its deadline can no longer be useful |
| 4 | **Adaptation only at the downstream boundary** | Bound our own demand on services we do not control, and treat their refusals as saturation rather than failure |

And four caller-visible outcomes that are **never merged**:

**ANSWERED** · **DEGRADED_BUT_ANSWERED** · **CAPACITY_REFUSED** · **TRUST_WITHHELD**

The last two are the ones systems usually collapse together, and they mean opposite things. `CAPACITY_REFUSED` is a
statement about **us** and carries retry guidance. `TRUST_WITHHELD` is a statement about **the request** and carries
none, because no amount of retrying makes it answerable.

## Why the trust path is structural

The easiest way to survive overload is to stop checking things. That is also how a system under pressure starts
answering questions it should have refused — and it is almost always introduced as a temporary measure by somebody
competent and tired.

So it is prevented by construction, not by policy:

- `serve()` is the **only** function in the system that can construct an answer;
- it runs eligibility → currency → citation **before** any content is returned;
- the degradation rung is a **parameter to the answer path**, applied after the trust path has already run;
- the capability set may only describe answer-path features, and **raises** if a trust-shaped switch is added to it.

There is no configuration key, environment variable, feature flag or operator action that reaches a trust check,
because there is nowhere to put one. `FX-3` exists to prove it: the mutation that tries is rejected.

## What was actually built

Seven parts. Each maps to a decision; none is optional without losing a lesson.

| Part | Responsibility |
|---|---|
| **P1** Admission controller | Permits per workload and per fairness domain; jittered retry-after; retry budget; single flight per caller |
| **P2** Burst buffer | Bounded by capacity and age; expired work leaves as an explicit outcome, before execution |
| **P3** Answer worker | Runs the trust path, then the answer path at the current rung |
| **P4** Downstream permit broker | Bounds concurrent calls and a token budget; reduces on throttling, restores gradually |
| **P5** Change-processing worker | The freshness workload, holding its floor and reporting its lag |
| **P6** Signals | Outcomes, queue age, concurrency, degradation level, freshness lag — and four alarms that stay distinct |
| **P7** Load generator | Deterministic scenarios; the teaching surface |

**Deliberately not built:** autoscaling policies, multi-region, warm pools, a caching layer, a dashboarding product,
priority tiers beyond the two workloads and the fairness domain, abuse controls, or production-scale load testing.

## The degradation ladder

| Rung | What changes | Still true |
|---|---|---|
| **NORMAL** | Nothing | Full trust path |
| **DEGRADED 1** | Retrieval breadth reduced; optional enrichment dropped | Full trust path; citations; complete answers |
| **DEGRADED 2** | Generation budget cut; suggestions off; downstream permits tightened | Full trust path; citations; a shorter answer |
| **SHED / REFUSE** | New work refused at admission | Admitted work completes normally |

Rungs rise immediately when a trigger is met and fall **one at a time**, only after the trigger has stayed clear for a
hysteresis interval — otherwise the system oscillates between rungs under a wobbling load.

At every rung, the trust path runs unchanged.

## Recovery is designed, not hoped for

Two rules, because recovery is where a handled incident becomes a second one:

- the backlog is disposed of **by age**, not replayed — replaying a backlog is how recovery outlasts the incident;
- permits return **in stages** with a dwell at each step, so the whole waiting population is not invited back at once.

Capacity and capability recover on **different clocks**: capacity follows the queue draining, capability follows the
pressure signal clearing with hysteresis. Tying them together makes recovery take twice as long as it should.

## What building it changed

The design was refined by contact with reality. These are recorded rather than smoothed over, because they are the
useful part:

| Finding | Consequence |
|---|---|
| **The account's Lambda concurrency quota made reserved concurrency unavailable** | The partition is enforced by application permits instead. The architecture is unchanged; its enforcement layer is not. See `README.md` — **cloud quotas are architectural constraints** |
| Re-queuing an item that could not be promoted **reset its deadline** | An item whose clock restarts can never expire — the age bound was unenforceable until this was fixed |
| Free capacity is not **available** capacity | A permit that is idle but owed to a quiet domain must stay idle, or that domain is starved the moment it returns |
| A saturation signal must be a **current condition** | Measured as a lifetime average, a system that had ever been saturated could never see itself recover |
| The degradation rung was only recomputed on arrival | A quiet system stayed at the rung its last burst reached — and recovery is exactly when nothing is arriving |

Every one of these is a way a system stays broken *after* the incident has passed. All were found by running it.

## Read next

`04-decisions/` holds the decision questions, the options that were considered and rejected, and ADR-001…ADR-008. Each
ADR records what was given up, which is the part usually missing from an architecture document.
