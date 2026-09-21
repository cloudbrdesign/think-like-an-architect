# Concepts first

**Read this before running anything.** Every term below appears in the lab, and the lab is much less useful if you meet
them for the first time inside a command. Each one is in plain English, with the misconception it usually replaces.

You do not need to memorise these. You need to have met them once, so that when the system refuses a request you know
*which* of these is happening.

---

## Load is not one number

| | |
|---|---|
| **Request rate** | How many requests arrive per second or minute. |
| **Concurrency** | How many requests are **in flight at the same time**. |

These are different, and confusing them is the most common capacity mistake. Ten requests per second, each taking one
second, means about ten in flight. Ten requests per second, each taking ten seconds, means about a hundred in flight —
the same rate, ten times the concurrency. **A slow answer holds resources; concurrency, not rate, is what exhausts
them.**

> A higher request rate does not automatically mean higher concurrency. Slower answers do.

## Measuring the promise

| | |
|---|---|
| **Latency** | How long one answer takes. |
| **Percentiles (p50, p95, p99)** | The median, and the slow tail. p95 = "95% of requests were at least this fast". |
| **Throughput** | How much work actually completes per unit time. |
| **Capacity** | The demand you can serve **within your promise** — not the maximum the machine can be pushed to. |
| **Headroom** | The margin you deliberately keep spare. |

> An average latency describes almost nobody's experience. The promise lives in the tail.
> Capacity is not a hardware property. It is a statement about a promise you intend to keep.

## Limits that are not yours

| | |
|---|---|
| **Quota** | A hard limit imposed by a platform or service. |
| **Throttling** | Refusing or slowing work once a limit is reached. |

Quotas are not performance settings, and they are not negotiable at runtime. Throttling is not a failure — it is a
**designed response** to a limit, and you will do it to your own callers in this lab.

> **Your application's capacity and the capacity of the things it calls are different numbers.** You can scale your own
> part perfectly and still be bounded by a service you do not control. This lab makes that boundary visible.

## What to do when there is more work than capacity

| | |
|---|---|
| **Queueing / buffering** | Holding requests until capacity frees up. |
| **Queue length** | How many items are waiting. |
| **Queue age** | How long the **oldest** waiting item has waited. |
| **Back-pressure** | Telling the caller to slow down instead of absorbing more than you can handle. |
| **Load shedding** | Deliberately refusing some work to protect the rest. |
| **Timeout** | Deciding when to stop waiting. |

> **A queue does not solve overload. It relocates it**, and turns it into latency. A queue with no bound turns it into
> unbounded latency, which is worse than a refusal because nobody is told.
>
> **Queue age is the signal that matters.** Length alone cannot tell you whether a queue is draining or stuck.
>
> Shedding is not failing. It is choosing *who* gets served, instead of letting everyone become equally slow.
>
> A long timeout is not generous. Work whose caller has already given up is capacity spent on nobody.

## What clients do to you

| | |
|---|---|
| **Retry amplification** | Retries multiplying load exactly when the system is weakest. |
| **Backoff** | Waiting longer between retries. |
| **Jitter** | Adding randomness so clients do not all return at the same instant. |

> Retrying is not always polite. A client that retries immediately on failure turns a survivable burst into an outage.
> Without jitter, every refused caller comes back together and rebuilds the burst that refused them.

## Staying useful under pressure

| | |
|---|---|
| **Graceful degradation** | Continuing with reduced function instead of failing entirely. |
| **Fairness and isolation** | Stopping one user, tenant or workload consuming everything. |
| **Recovery and draining** | Returning to normal afterwards, including the backlog. |

> Degrading does not mean relaxing correctness. In this lab you will see a system drop optional capability while its
> **trust checks keep running unchanged** — that distinction is the whole point of the episode.
>
> "First come, first served" is not fair when one caller arrives ten thousand times.
>
> When load drops, service is **not** instantly normal. Recovery is something you design, or something that hurts.

---

## The four answers this system can give

Most systems have two outcomes: it worked, or it broke. That is not enough, and the ambiguity is expensive. This lab
gives four, and never merges them:

| Outcome | Means | It is a statement about |
|---|---|---|
| **ANSWERED** | Full answer, all checks passed | — |
| **DEGRADED_BUT_ANSWERED** | Answer produced with reduced capability, and it says what was reduced | our capacity |
| **CAPACITY_REFUSED** | *"I cannot serve this request now."* Carries retry-after guidance | **us** |
| **TRUST_WITHHELD** | *"I must not answer this request."* Carries **no** retry-after | **the request** |

The last two look similar in a log and mean opposite things. One says *come back shortly*. The other says *no amount of
retrying will make this answerable*. An operator who cannot tell them apart cannot respond correctly to either — and a
system that merges them will, under pressure, quietly start answering things it should have refused.

**Watch for this specifically in the lab.** It is the difference between a system that degrades and a system that
betrays you.
