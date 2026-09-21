# Implementation Design (E3 — build authorisation design) — Kestrelmoor: answering under production traffic

**Status:** design, 2026-09-20.

**Goal.** The **smallest** implementation that makes the approved architecture observable and teachable. Not a miniature
production platform. Every component must earn its place by demonstrating an accepted architectural decision
(ADR-001…008).

---

## 1. Designed backwards from the lesson: the nine observations

The implementation exists to make these observable in one lab session. Each scenario names the decisions it
demonstrates and the outcome the learner should see.

| # | Scenario | What the learner observes | Demonstrates |
|---|---|---|---|
| **A** | **Normal** | Requests admitted; trust checks run; answers returned; freshness work progressing | ADR-001 promise · baseline for everything else |
| **B** | **Short burst** | Some work admitted now, some **buffered briefly**, some **refused** — three visibly different fates | ADR-002 · the buffer is small and visible |
| **C** | **Sustained overload** | The buffer hits its bound and its age limit; excess is **refused explicitly**; the system does not just get slower | ADR-002 · LOD-002 · FX-1 contrast |
| **D** | **Retry amplification** | `bad-retry` multiplies offered load and collapses useful throughput; `bounded-retry` keeps it stable | ADR-006 · FX-2 |
| **E** | **Workload contention** | Answering and change processing both keep their floor; neither consumes the system; freshness lag grows **visibly** | ADR-003 · FRS-C-001/002 |
| **F** | **Downstream limit** | The model-service boundary becomes the constraint; admission responds; application capacity ≠ downstream capacity | ADR-005 · TP-15 |
| **G** | **Degradation** | Optional capability drops away by rung; trust checks still run on every answer | ADR-004 |
| **H** | **Trust withhold under load** | A request that cannot satisfy currency returns **TRUST_WITHHELD** while the system is saturated — never `DEGRADED_BUT_ANSWERED` | ADR-004 · a recorded decision · FX-3 contrast |
| **I** | **Recovery** | Backlog ages out and drains; staged return; no stampede; freshness catches up; normal resumes | ADR-008 |

**Component rule:** if a component supports none of A–I, it is not built.

## 2. The four caller-visible outcomes

| Outcome | Meaning | Carries |
|---|---|---|
| **ANSWERED** | Full answer, trust checks passed | citations; capacity state |
| **DEGRADED_BUT_ANSWERED** | Answer produced with reduced capability | citations; **what was reduced**; degradation level |
| **CAPACITY_REFUSED** | *"I cannot serve this request now."* | reason=capacity; retry-after (jittered); no content |
| **TRUST_WITHHELD** | *"I must not answer this request."* | reason=currency/eligibility; **no** retry-after implying it would succeed later by retrying harder |

**These are never collapsed.** Counted separately, alerted separately, rendered differently in the load generator's
output. Merging them is the single most likely implementation defect, and TST-404 exists to catch it.

## 3. Smallest implementation (conceptual)

Seven parts. Each maps to a decision; none is optional without losing a scenario.

| Part | Responsibility | Why it exists |
|---|---|---|
| **P1 Admission controller** | Permits per fairness domain and workload partition; issues CAPACITY_REFUSED with jittered retry-after; enforces the retry budget; single-flight per user | ADR-001, 002, 003, 006 |
| **P2 Burst buffer** | Small, explicitly bounded by **capacity and age**; expired work leaves as CAPACITY_REFUSED (explicit outcome, never silent) | ADR-002, a recorded decision |
| **P3 Answer worker** | Runs the **trust path** then the **answer path**; applies the degradation rung; emits the outcome | ADR-004 |
| **P4 Downstream permit broker** | Bounds concurrent model-service calls and token budget; reduces adaptively on throttling; classifies rejection as saturation | ADR-005 |
| **P5 Change-processing worker** | The Episode 03 workload at lab scale; holds its floor; reports freshness lag and watermark | ADR-003, FRS-C |
| **P6 Signals** | Per-request timestamps and outcomes; queue age; concurrency; shed reasons; lag; retry-budget state | ADR-007 |
| **P7 Load generator** | Deterministic scenario driver and teaching display | §7 |

**Reused, not rebuilt:** the Episode 02 eligibility logic and the Episode 03 authority/currency logic are carried over as
the trust path. Episode 04 adds no new trust code — that is the point of ADR-004.

## 4. The degradation ladder (precise)

| Rung | What changes | Why | Trigger | Remains available | Becomes unavailable | Signal | Recovery |
|---|---|---|---|---|---|---|---|
| **NORMAL** | Nothing | Baseline | Utilisation below L1 threshold, buffer age near zero | Everything | — | `degradation_level=0` | n/a |
| **DEGRADED 1** | Retrieval breadth reduced; optional enrichment/re-ranking dropped | Cheapest capability to lose; largest latency saving per unit of quality | Buffer age above the L1 bound **or** admitted concurrency at the partition ceiling for a sustained interval | Full trust path; citations; complete answers | Enrichment; widest retrieval | `degradation_level=1` + reason | Falls back to 0 only after the trigger clears for the hysteresis interval |
| **DEGRADED 2** | Generation budget cut (shorter answers); follow-up suggestions off; downstream permits tightened | Protects the downstream boundary and shortens hold time per request | L1 persists **or** downstream rejection rate above its bound | Full trust path; citations; a shorter answer | Long answers; suggestions | `degradation_level=2` + reason | Steps down one rung at a time, each after the hysteresis interval |
| **SHED / REFUSE** | New work refused at admission | Capacity is committed; refusing is cheaper and more honest than queueing | Buffer at capacity or age bound; or no permit free | Admitted work completes normally | New admissions in that domain | `CAPACITY_REFUSED` + reason + retry-after | Staged ramp (ADR-008) |

**Mechanically constrained:** the rung is a single value computed from signals; each rung's effect is a set of *feature
switches on the answer path only*. The trust path is not addressable from the rung — there is no configuration key that
maps to it. **Operators may reduce service; operators may not reduce trust**.

## 5. The non-degradable trust path

Executed on every answer, in this order, before any content is returned:
1. **Eligibility** from current grants (Episode 02).
2. **Currency** against authority; only *known current* is servable (Episode 03).
3. **Citation** of what was used.
4. **Outcome classification** — and if 1 or 2 cannot be established: **TRUST_WITHHELD**, whatever the load.

**Structural enforcement:** answers can only be emitted by the single function that runs this sequence; the degradation
switches are parameters to the *answer path*, which runs after it. No rung, flag, environment variable or operator
action can construct a response that skips it. **TST-404 and FX-3 exist to prove this, and FX-3 must fail the suite.**

## 6. Demonstration parameters (tiny by design)

**These are DEMONSTRATION PARAMETERS, not production recommendations.** They are chosen so a learner can reach every
state in minutes, at negligible cost.

| Parameter | Lab value | Why this value |
|---|---|---|
| Answering permits (total) | **4 concurrent** | Small enough that a handful of requests saturates it |
| Fair share per depot | **2 concurrent**, 2 depots | One depot alone cannot take the whole pool |
| Change-processing floor | **1 concurrent** | Visibly survives an answering flood |
| Elastic middle | **1 concurrent** | Borrowable, reclaimed promptly |
| Buffer capacity | **6 items** | Fills within seconds of a burst |
| Buffer max age | **10 s** | Expiry is observable inside a demo |
| Promise (lab objective) | **p95 ≤ 8 s for admitted work** (measured, not asserted) | Derived from lab answer duration; the architecture owns the promise, the lab demonstrates it |
| Downstream permits | **2 concurrent model calls**, token budget per minute | Makes the downstream boundary reachable without large spend |
| Retry budget | **1 retry per request identity per 30 s** | `bad-retry` visibly exceeds it |
| Degradation thresholds | L1 at buffer age > 3 s; L2 at > 6 s or downstream rejects > 20% | Both rungs reachable in a burst |
| Hysteresis | **15 s** at each step down | Oscillation is visible if removed |
| Recovery ramp | 2 → 3 → 4 permits, **10 s** per step | Staged return is observable |

Every one of these appears in one configuration file, labelled *demonstration parameters*, so the learner can change one
value and watch the behaviour move.

## 7. Load generator (teaching instrument, not a benchmark)

**Scenario commands, not knobs:** `normal · burst · sustained · bad-retry · bounded-retry · contention · downstream-limit
· degrade · withhold · recover`. Each is deterministic: fixed seed, fixed arrival pattern, fixed question set.

**Live display** — the learner must be able to read the lesson without any external observability product:

```
t+12s  offered 18  admitted 4  buffered 3  answered 11  degraded 2
       capacity-refused 5  trust-withheld 1  retried 2
       concurrency 4/4   buffer age 6.2s (max 10s)   downstream 2/2 permits
       freshness lag 41s   watermark stalled: yes   degradation level 1
```

Every counter maps to an outcome or a signal in §2 and §6; nothing is displayed that the architecture does not define.
The generator also writes a small per-run JSON summary so a test can assert on it.

**Not built:** arbitrary throughput benchmarking, percentile distribution studies, or a general-purpose load tool.

## 8. AWS mapping (after the conceptual design)

**Region: `us-east-1`** (established Season 1 default). It is set explicitly everywhere, because the workstation
profile defaults to `af-south-1`.

Each mechanism below was checked against AWS documentation on the date of the design; verify against current
documentation for your own region before relying on any of it.

| Part | Candidate mechanism | Architectural requirement it serves |
|---|---|---|
| P1 Admission | Application-level permit logic in the answering function, with API Gateway throttling as a cheap outer filter only | *Admission is ours; the edge is a filter, not the guarantee* (its throttling is documented best-effort) |
| P2 Buffer | SQS standard queue, message timestamped with a deadline; consumer discards expired items **before** execution and emits CAPACITY_REFUSED | *Bounded by age; expired work leaves through an explicit outcome* |
| P3 Answer worker | Lambda function with **reserved concurrency** = answering partition size | *A partition cannot exceed or be starved of its permits* |
| P4 Downstream broker | In-process permit counter plus adaptive reduction on model-service `ThrottlingException`; token budget tracked per minute | *Bound our own demand on a boundary we do not control* |
| P5 Change processing | Separate Lambda function with its own reserved concurrency (the floor) | *Floors for both workloads* |
| P6 Signals | Custom metrics (outcomes, queue age, degradation level, lag) + SQS `ApproximateAgeOfOldestMessage`; four alarms | *Queue age leads where queueing exists; multiple signals, never depth alone* |
| P7 Load generator | Local Python CLI in the learner package | *Deterministic scenarios; teaching output* |

**Fairness note:** SQS now documents **fair queues** (`MessageGroupId` on standard queues, with noisy/quiet-group
metrics). That is a candidate mechanism for the fairness domain and is recorded as an option for the build,
not as the principle: the principle remains *one fairness domain must not consume the capacity needed by all others*.

## 9. What is deliberately not built
- No autoscaling policies, no multi-region, no warm pools, no caching layer.
- No dashboarding product; the load generator's display is the teaching surface.
- No tiering, no priority classes beyond the two workloads and the fairness domain.
- No abuse controls, WAF or bot management (ASM-009, MT-03).
- No production-scale load testing (CON-007).
- No new trust logic: Episodes 02 and 03 provide it unchanged.
