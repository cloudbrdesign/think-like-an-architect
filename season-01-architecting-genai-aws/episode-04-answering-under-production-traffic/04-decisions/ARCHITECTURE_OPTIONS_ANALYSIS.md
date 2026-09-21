# Architecture Options Analysis — Kestrelmoor Knowledge Assistant: answering under production traffic

**Status:** **APPROVED and FROZEN** (2026-09-20). The recommended combination was approved and is
not to be collapsed into one pure option for implementation convenience.

**Method.** The problem is solved conceptually first. No option is described in terms of AWS services; the mapping is a
separate layer ([`../03-architecture/TARGET_ARCHITECTURE.md`](../03-architecture/TARGET_ARCHITECTURE.md) §B). Each option
is a genuinely different answer to "where does pressure go when demand exceeds capacity", not a restyling of one design.

**Blocking criteria** (an option that fails any of these is not viable):

| Criterion | From |
|---|---|
| **B1** No answer is served that has not passed request-time eligibility and currency | LOD-001, SEC-001, a recorded decision |
| **B2** A request that will not be served is refused explicitly and promptly; no silent timeout | LOD-002, a recorded decision |
| **B3** Excess demand is handled by a stated rule; queueing, where it exists, is bounded | LOD-004 |
| **B4** Retries are bounded by the architecture, not by client goodwill | LOD-007 |
| **B5** Answering and change processing each keep a floor; neither can be starved indefinitely | FRS-C-001, a recorded decision |

Secondary criteria: downstream protection (LOD-006), fairness (LOD-008), observability (LOD-010, OPS-001), bounded
recovery (NFR-003), operational complexity (CON-004), cost (CON-006), teaching value.

---

## Option 1 — Direct admission with immediate shedding

Every request is admitted or refused at the front door against a live concurrency budget. There is no waiting room: if
no permit is free, the caller is refused immediately with retry guidance. Work in flight is never queued behind other
work.

| | |
|---|---|
| **What it optimises** | Predictable latency for admitted work; the simplest mental model; cheap refusals; the shortest path from saturation to caller feedback |
| **What it sacrifices** | Throughput smoothing. A four-minute shift-start spike is refused wholesale even though it would have fitted inside a two-minute buffer. Users at 07:00 see refusals rather than a short wait |
| **How it fails under overload** | Gracefully but bluntly: refusal rate climbs in proportion to excess demand. No collapse, no unbounded latency |
| **Answering** | Protected for admitted requests; the promise holds exactly at the stated concurrency |
| **Freshness** | Needs a separate budget, or change processing simply competes for the same permits (fails B5 alone) |
| **Retries** | Pushes the whole retry problem outward: mass refusal at 07:00 means mass retry at 07:00 + retry-after. Requires strong retry governance to be safe |
| **Downstream protection** | Good: the permit count is chosen from downstream capacity, so downstream is never oversubscribed |
| **Operational complexity** | Lowest. One number to set, one to observe |
| **Cost** | Lowest: no buffer infrastructure, no idle capacity |
| **Teaching value** | High for admission control and back-pressure; weak on queueing and the difference between rate and concurrency |
| **Blocking criteria** | B1 ✓ · B2 ✓ · B3 ✓ · B4 partial (needs the retry contract) · **B5 ✗ on its own** |

## Option 2 — Bounded-age queue in front of a fixed worker pool

Requests enter a waiting room with a hard age bound. Workers pull the newest viable work; anything whose remaining
promise budget has expired is discarded **before** it is executed, and its caller is told. The queue absorbs bursts and
converts them into slightly higher latency instead of refusals.

| | |
|---|---|
| **What it optimises** | Burst absorption: a short, sharp spike is served rather than refused. Useful work per unit capacity |
| **What it sacrifices** | Latency predictability, and simplicity. A queue is a second place where policy lives, and where user questions are stored (DATA-002) |
| **How it fails under overload** | Well if the age bound holds; catastrophically if it does not. An unbounded or age-blind queue converts overload into a long, useless wait and spends capacity on abandoned work — precisely FX-1 |
| **Answering** | Good at the designed burst; degrades to Option 1 behaviour when the queue is full |
| **Freshness** | Same weakness as Option 1: without partitioning, change processing and answering contend for the same workers |
| **Retries** | Better than Option 1 at the spike (fewer refusals to retry against), but a queue plus retries is the classic amplification trap |
| **Downstream protection** | Indirect: worker count bounds downstream concurrency |
| **Operational complexity** | Moderate: age bounds, discard policy, queue-age monitoring, retention limits on stored questions |
| **Cost** | Low to moderate |
| **Teaching value** | Very high: queue age versus queue length, pre-execution expiry, and why a queue relocates overload rather than solving it |
| **Blocking criteria** | B1 ✓ · B2 ✓ (only with pre-execution expiry and notification) · B3 ✓ (bounded) · B4 partial · **B5 ✗ on its own** |

## Option 3 — Partitioned capacity with fair share

Capacity is divided into named pools before any request arrives: an answering pool, a change-processing floor, and a
reserve. Within answering, each depot (or tenant class) has a fair share of the pool, so no single source can consume
everything. Excess demand in one partition is refused in that partition while other partitions keep serving.

| | |
|---|---|
| **What it optimises** | Isolation and predictability: the bulletin depot cannot deny the other ten; freshness cannot be starved; the blast radius of any overload is one partition |
| **What it sacrifices** | Utilisation. Reserved capacity sits idle when its partition is quiet, unless borrowing is allowed — and borrowing re-introduces the coupling the partitions exist to prevent |
| **How it fails under overload** | Partition by partition, visibly. The system as a whole never loses all answering capacity |
| **Answering** | Always retains its floor, even during the largest change burst |
| **Freshness** | Always retains its floor; when it is slowed, the Episode 03 watermark stalls **visibly** (FRS-C-002) |
| **Retries** | Neutral: still needs the retry contract, but fair share caps how much damage one misbehaving client population can do |
| **Downstream protection** | Strong: each pool's permits are sized against the downstream budget, so the sum cannot exceed it |
| **Operational complexity** | Highest of the first three: more knobs, and an allocation that must be reviewed as traffic changes |
| **Cost** | Moderate: some capacity is deliberately idle |
| **Teaching value** | Very high: it is the answer to "whose request gets refused", and it makes the answering-versus-freshness trade-off concrete |
| **Blocking criteria** | B1 ✓ · B2 ✓ · B3 ✓ · B4 partial · **B5 ✓** |

## Option 4 — Adaptive control driven by downstream signals

No fixed capacity number. The system continuously infers its safe concurrency from observed latency and downstream
rejection, raising the limit while healthy and lowering it the moment the model service or records system begins to
throttle. Admission follows the inferred limit.

| | |
|---|---|
| **What it optimises** | Utilisation and truthfulness: the limit tracks what the platform will actually give today, including quota changes we did not make |
| **What it sacrifices** | Predictability and explicability. The promise becomes "whatever the controller currently believes", which is hard to state to a depot manager and harder to teach |
| **How it fails under overload** | Usually well; but a controller can oscillate, and it can mistake a slow dependency for saturation, throttling the system for the wrong reason |
| **Answering** | Good average behaviour, weaker worst-case guarantees |
| **Freshness** | No inherent protection: a controller optimising answering latency will happily starve background work |
| **Retries** | Neutral |
| **Downstream protection** | Strongest of all options: it reacts to the real boundary rather than to an assumed one |
| **Operational complexity** | High: tuning, damping, and a failure mode where the controller itself is the incident |
| **Cost** | Moderate |
| **Teaching value** | High but advanced; risks teaching control theory instead of architecture |
| **Blocking criteria** | B1 ✓ · B2 ✓ · B3 ✓ (the rule is "admit to the inferred limit") · B4 partial · **B5 ✗ on its own** |

## Option 5 — Accept-now, deliver-later (asynchronous answering)

The API accepts the question, returns a ticket immediately, and delivers the answer when capacity allows — by
notification or polling. Overload becomes a longer wait for delivery rather than a refusal.

| | |
|---|---|
| **What it optimises** | Never saying no. Throughput smoothing across the whole peak, and a natural place to coalesce duplicate questions |
| **What it sacrifices** | The product. A technician standing at a points machine needs the answer now; a ticket is not an answer. It also changes the client contract for every caller, and moves the trust checks away from the moment of asking — eligibility and currency must be evaluated at **delivery** time, not acceptance time, or the answer can be stale or over-permissive on arrival (B1 risk) |
| **How it fails under overload** | Quietly: the backlog grows, tickets age, and users are left waiting without the system ever admitting it is saturated |
| **Answering** | Throughput preserved, usefulness degraded |
| **Freshness** | Neutral, though a long backlog makes currency at delivery harder to guarantee |
| **Retries** | Best case: a ticket removes the incentive to retry entirely |
| **Downstream protection** | Good: the backlog is drained at whatever rate downstream allows |
| **Operational complexity** | High: delivery channel, ticket lifecycle, retention of pending questions, re-checking trust at delivery |
| **Cost** | Moderate to high |
| **Teaching value** | High as a contrast: it shows that "availability" can be bought by changing what the product promises, which is a real architectural choice — and why this engagement rejects it for the interactive path |
| **Blocking criteria** | B1 **at risk** (trust must be re-evaluated at delivery) · B2 ✓ (acceptance is explicit) · B3 ✓ · B4 ✓ · B5 ✗ on its own |

---

## Comparison against the blocking criteria

| | B1 trust | B2 explicit refusal | B3 bounded excess | B4 bounded retries | B5 both floors | Verdict |
|---|---|---|---|---|---|---|
| 1 Direct admission | ✓ | ✓ | ✓ | with contract | ✗ | Viable spine, incomplete alone |
| 2 Bounded-age queue | ✓ | ✓ with expiry | ✓ | with contract | ✗ | Useful component, not a whole answer |
| 3 Partitioned capacity | ✓ | ✓ | ✓ | with contract | ✓ | **Only option that satisfies B5 by construction** |
| 4 Adaptive control | ✓ | ✓ | ✓ | with contract | ✗ | Best answer to the downstream boundary |
| 5 Accept-now-deliver-later | at risk | ✓ | ✓ | ✓ | ✗ | Changes the product; rejected for the interactive path |

**No option is a straw man.** Options 1, 2, 4 and 5 are each the right answer to a different question; they fail here
only against the whole criteria set. Option 5 in particular is a defensible design for a different product, and its
rejection is a product decision, not a technical dismissal.

## Recommendation

**Partitioned capacity (Option 3) as the spine, with direct admission (Option 1) as the default behaviour inside each
partition, a narrow bounded-age buffer (Option 2) only for the shift-start burst, and adaptive reduction (Option 4) at
the downstream boundary only.**

**Why this combination, and not one pure option:**
- **Option 3 alone** satisfies B5, the requirement the incident actually exposed, so it must be the spine.
- **Inside a partition**, direct admission is the honest default: if the answer cannot be produced within the promise,
  say so now.
- **A small, age-bounded buffer** earns its place only where the burst is short and predictable (shift start). It is
  sized in seconds of promise budget, not in requests, and work is discarded before execution when it can no longer be
  served in time.
- **Adaptive reduction applies only to the downstream permit count**, where the limit is genuinely unknowable in advance
  (ASM-006, RR-13). The user-facing promise stays a stated number, so it can be explained, tested and taught.

**The price, stated plainly:**
- some capacity is deliberately idle (Option 3's cost), and utilisation is lower than Option 4 alone would achieve;
- there are more knobs than Option 1, and an allocation review becomes an operational task (CON-004);
- the buffer stores user questions briefly, which brings retention obligations (DATA-002, ASM-010);
- refusals at the peak are real and visible: this design chooses an honest refusal over an ambiguous wait, and some
  users will be refused at 07:00.

**What this does not decide:** the actual allocation numbers, the buffer's age bound, the fair-share granularity and the
adaptive controller's parameters. Those are measured at the implementation and validation gates,
not asserted here.
