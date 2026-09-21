# Target Architecture — Kestrelmoor Knowledge Assistant: answering under production traffic

**Status:** **APPROVED and FROZEN** (2026-09-20); ADR-001…008 ACCEPTED in direction. Architectural thesis:
**finite capacity requires an explicit service contract**.

**Reading order.** §A is the architecture. §B maps it to AWS. **The architecture in §A must make sense with every AWS
name removed** — that is the test this document is written to pass.

---

# §A — Conceptual architecture

## A1. The two contracts, and how they meet

| Question | Owner | Decides |
|---|---|---|
| *May this answer be given to this person, from this content, right now?* | Episodes 02 + 03 | **Whether an answer is allowed** |
| *Does the system have capacity to attempt that work now?* | Episode 04 | **Whether it is attempted** |

They compose in one direction only: capacity can stop work from being attempted; it can never make a disallowed answer
allowed. **Degrade capability, not trust** (ADR-004).

## A2. The request path

```
CALLER
  │  question + attempt identity (ADR-006)
  ▼
┌──────────────────────────────────────────── ADMISSION (ADR-002) ────────────────────────────────────────────┐
│  Is a permit free in this caller's partition?          (partition + fair share — ADR-003)                   │
│    yes → admit, stamp deadline                                                                              │
│    no  → is the short burst buffer within its age bound?                                                     │
│             yes → hold briefly (age-bounded, discard before execution if the deadline cannot be met)        │
│             no  → REFUSE: typed "capacity", retry-after (jittered), cheap        ──────────────► CALLER     │
└──────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
  │ admitted (bounded concurrency)
  ▼
┌──────────────────────── TRUST PATH — never degraded (ADR-004) ────────────────────────┐
│  eligibility from current grants (Episode 02)                                         │
│  currency check against authority (Episode 03) ── cannot confirm ──► WITHHOLD ──────► CALLER
│  four-state rule: only *known current* is served                                      │
└───────────────────────────────────────────────────────────────────────────────────────┘
  │ permitted, current
  ▼
┌──────────────── ANSWER PATH — may degrade (capability only) ─────────────────┐
│  retrieval (breadth may be reduced)                                          │
│  optional enrichment / re-ranking (may be dropped)                           │
│  generation (budget may be reduced)      ── downstream permits (ADR-005) ──► MODEL SERVICE (own quota)
└──────────────────────────────────────────────────────────────────────────────┘
  ▼
RESPONSE: answer │ degraded answer (states what was reduced) │ refusal (typed) │ withheld (not current)
```

**The freshness workload, sharing the same finite capacity:**

```
RECORDS SYSTEM (authority) ──changes──► CHANGE PROCESSING ──► INDEX (derived copy)
        ▲                                     │
        │ currency checks (request path)      │ reconciliation + repair (Episode 03)
        └──────────── shared, finite ─────────┘
                    contention point (ASM-007)
```

Both workloads draw permits from one budget, split by ADR-003: **answering floor · elastic middle · change-processing
floor**. When change processing is held to its floor, the Episode 03 watermark stalls **visibly** and alerts.

## A3. Capacity boundaries and pressure

| # | Boundary | What is finite | What happens at the limit |
|---|---|---|---|
| 1 | Admission | permits per partition | refuse (typed) or hold briefly within the age bound |
| 2 | Burst buffer | **age**, not length | discard before execution; tell the caller |
| 3 | Trust path | records-system capacity for currency checks | withhold (Episode 03 rule), counted as a capacity outcome |
| 4 | Answer path | our own concurrency | degrade capability by the ladder |
| 5 | Downstream boundary | model-service and records-system quotas | permits reduce adaptively; rejections classified as saturation |
| 6 | Change processing | its floor plus elastic share | freshness lag grows **visibly**; watermark stalls; alert |

**Pressure may accumulate in exactly two places** — the burst buffer (bounded by age) and the change-processing backlog
(bounded by its floor and visible as lag). Nowhere else is allowed to grow silently: not in client connections, not in
downstream retries, not in an internal queue.

## A4. Retry ownership

Retries belong to the architecture, not to the caller's discretion (ADR-006): the server issues jittered guidance,
enforces a budget, recognises a repeated attempt by its identity, and coalesces identical in-flight questions from the
same user. Clients implement backoff with jitter; the design does not depend on their doing so.

## A5. Saturation and recovery

- **Lead signal:** age of the oldest admitted-but-unstarted work (ADR-007).
- **Beside it:** admitted concurrency vs permits · shed rate by reason · downstream rejection rate · tail latency ·
  freshness lag and watermark age · retry-budget exhaustion.
- **Four distinct alerts:** answering saturation · downstream quota exhaustion · stalled watermark · failed recovery.
- **Recovery (ADR-008):** discard non-viable backlog → staged admission ramp with settle periods → hysteresis when
  restoring capability → staggered retry guidance → scheduled freshness catch-up inside its share. "Recovered" means the
  promise holds at the stated capacity.

## A6. What the architecture promises (ADR-001)

- an **admitted capacity**, stated as concurrency (with the equivalent rate for planning);
- a **p95 promise** for admitted requests, measured by a recorded method;
- four possible outcomes, always explicit: **answer · degraded answer · refusal (capacity) · withheld (not current)**;
- and one guarantee that survives every other mechanism: **nothing is served that has not passed eligibility and
  currency**.

---

# §B — AWS mapping (a separate layer)

**Architectural requirement vs current AWS mechanism.** Everything in §A stands without this section. Below, each
responsibility is mapped to a *candidate current mechanism*. A product limitation is never presented as the
architectural principle.

| # | Architectural responsibility (§A) | Candidate AWS mechanism | Architectural requirement being met |
|---|---|---|---|
| 1 | Admission and cheap typed refusal at the edge | API Gateway request throttling (account/stage/method; usage plans per client) returning `429` | *Refuse before expensive work, cheaply, with a typed response* |
| 2 | Bounded concurrency per partition | Lambda **reserved concurrency** per function (a partition = a function or an alias with its own reservation) | *A partition cannot exceed its permits, nor consume another's* |
| 3 | Answering / change-processing floors | Separate reserved-concurrency allocations for the answering and change-processing functions, sized from one budget | *Floors that neither workload can take from the other* |
| 4 | Short, age-bounded burst buffer | A queue with per-message deadline metadata and pre-execution expiry, or an in-process bounded waiting room | *Bounded by age, discarded before execution* |
| 5 | Downstream permits and adaptive reduction | Client-side concurrency permits in the answering code around model-service calls, plus adaptive reduction on `ThrottlingException` | *We never become the cause of our own downstream throttling* |
| 6 | Trust path (unchanged) | The Episode 02 eligibility check and the Episode 03 authority check, unchanged | *Never degraded* |
| 7 | Retry budget, guidance, attempt identity, single flight | Server-side budget keyed by client population; `Retry-After`-style guidance with jitter; idempotency key carried by the caller | *Retries bounded by the architecture* |
| 8 | Signals and alerts | Per-request timestamps and deadlines emitted as metrics; four named alarms | *Queue age leads; causes stay distinct* |
| 9 | Overload demonstration at small scale | Deliberately tiny quotas, permits and reservations in the lab | *Reproduce the behaviour cheaply and safely* |

## B1. Dated platform currency check (2026-09-20)

Read-only documentation checks. **No AWS API call was made**, and nothing was deployed.

| Claim used in the mapping | Finding (AWS documentation, read 2026-09-20) | Consequence |
|---|---|---|
| The model service enforces its own quotas per account and region (ASM-006) | *Quotas for Amazon Bedrock*: quotas are per account, model inference "is controlled by quotas on token usage", and the service exposes two inference endpoints (`bedrock-runtime`, `bedrock-mantle`) whose traffic is "tracked against separate quotas, even when calling the same underlying model". Defaults "might be updated depending on regional factors, payment history…" and increases are requested through Service Quotas | ASM-006 holds. **Token-based** quotas mean our permit model must bound tokens as well as calls — recorded for E3 sizing. The two-endpoint split is a mechanism detail, not an architectural principle |
| Edge throttling can refuse cheaply with a typed response | *Throttle requests to your REST APIs*: token-bucket throttling per account and Region, configurable per stage/method and per client via usage plans; clients "may receive `429 Too Many Requests`". Throttles are "applied on a best-effort basis and should be thought of as targets rather than guaranteed request ceilings" | Usable for the outer defence, **but not as the guarantee**. The architecture's own admission control (ADR-002) remains the authoritative boundary; the edge is a cheap first filter |
| Per-partition concurrency ceilings and floors exist | *Understanding Lambda function scaling*: default 1,000 concurrent executions per Region per account; **reserved concurrency** "sets the maximum and minimum number of concurrent instances… no other function can use that concurrency"; provisioned concurrency pre-initialises environments; requests-per-second is capped at 10× concurrency; scaling rate 1,000 instances / 10 s per function | Reserved concurrency implements ADR-003's floors directly. The 10× RPS relationship and the scaling rate are sizing inputs for E3, and the scaling rate is a further reason the burst buffer exists |
| Concurrency, not request rate, is the binding unit (ASM-005, ADR-001) | Same page: `Concurrency = average requests per second × average duration`, and the explicit note that "concurrency differs from requests per second" | Confirms the promise's unit. This is the platform agreeing with the architecture, not the source of it |
| A queue with per-item deadlines for the burst buffer | **NOT VERIFIED at this gate.** No documentation check was performed for the queue service's retention, visibility and metadata behaviour | Recorded as an open item for E3; the buffer may equally be in-process. The architecture requires *age-bounded, discarded before execution*, by whatever mechanism |

**Rule applied:** where a mechanism and the requirement differ, the requirement wins. Edge throttling being best-effort,
quotas being token-based, and concurrency scaling being rate-limited are all *implementation facts to design around* —
none of them changes what the architecture must promise.

## B2. What is deliberately not decided here
- Allocation numbers (floors, fair shares, permits, buffer age bound, ramp steps): measured at the validation gate.
- Whether the buffer is a queue service or in-process.
- Whether the answering path is split into more than one partitioned unit.
- Any account, region, stack or resource naming: E3.
