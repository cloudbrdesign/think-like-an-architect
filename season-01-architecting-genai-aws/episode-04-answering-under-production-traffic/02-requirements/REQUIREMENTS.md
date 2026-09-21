<!-- template: tla-requirements/1 -->
# Requirements — Kestrelmoor Knowledge Assistant: answering under production traffic

**Status:** **APPROVED and FROZEN** (2026-09-20) — the Episode 04 baseline requirement set.
Future additions must trace to the business problem, a stakeholder, a constraint, a discovered risk, a validation finding
or a product-owner ruling.

**Rules for this set**
- **What, not how:** requirements state what must be true, never which service or mechanism provides it. IDs are stable
  once approved.
- **Source column:** names the objective (OBJ-n in the brief), a stakeholder, a constraint, or an inherited item from an
  earlier episode (Episode 01 RR-13, Episode 02 TS-E02-08, the Episode 03 bridge).
- **Validation theme:** names a proposed theme in [`../06-validation/VALIDATION_PLAN.md`](../06-validation/VALIDATION_PLAN.md).
  Test IDs are assigned at the validation design gate, not here.
- **Related questions:** names decision questions in
  [`../04-decisions/ARCHITECTURE_DECISION_QUESTIONS.md`](../04-decisions/ARCHITECTURE_DECISION_QUESTIONS.md).
- **INVARIANT:** marks a property that must hold at all times, including during overload, degradation and recovery.
  Each invariant needs a test shown able to fail.
- **Numbers:** every figure is a working value for this fictional engagement (ASM-001 … ASM-011), never a universal or
  industry requirement.

**Vocabulary** (defined for the learner in the brief's teaching prerequisites)
- **admitted request** — a request the system has accepted and intends to answer within its promise;
- **shed request** — a request refused explicitly and promptly because capacity is committed elsewhere;
- **degraded answer** — an answer produced with reduced function, still satisfying every eligibility and currency check;
- **promise** — the stated latency and outcome the system commits to for admitted requests at or below its stated
  capacity;
- **change processing** — the Episode 03 workload: change application, reconciliation, repair and rebuild.

## Business

| ID | Requirement | Rationale | Priority | Source | Validation theme | Related questions |
|---|---|---|---|---|---|---|
| BUS-001 | At shift start, a depot technician either receives an answer within the stated promise or is told immediately that the assistant cannot take the request now, and when to retry | The incident's real harm was an unbounded wait with no information | MUST | OBJ-1 · OBJ-3 · Depot technicians | VT-1, VT-2 | DQ-A, DQ-D |
| BUS-002 | A safety bulletin reaches staff during the same period in which its change processing runs | Bulletins create both the load and the reason for the load | MUST | OBJ-4 · Head of Engineering Safety | VT-5 | DQ-F |
| BUS-003 | Company-wide use continues at the assumed daily peak without planned interruption, and without depots needing local workarounds | Rollout must hold (OBJ-1) | MUST | OBJ-1 · COO | VT-1 | DQ-A, DQ-C |
| BUS-004 | Kestrelmoor can state, before a rollout or campaign, how much demand the assistant can serve | Capacity planning must not require an incident | SHOULD | OBJ-6 · Platform Engineering | VT-7 | DQ-G |

## Functional

| ID | Requirement | Rationale | Priority | Source | Validation theme | Related questions |
|---|---|---|---|---|---|---|
| FUN-001 | Every response states whether it is a full answer, a degraded answer or a refusal, and a refusal carries a machine-readable reason | Clients and users must distinguish "not now" from "no" and from "broken" | MUST | OBJ-3 · Depot technicians · Platform Engineering | VT-2, VT-3 | DQ-D, DQ-E |
| FUN-002 | A refusal caused by capacity includes retry guidance the client is required to honour | Without guidance, clients invent their own and amplify (RSK-01) | MUST | OBJ-3 | VT-3 | DQ-E |
| FUN-003 | A degraded answer says what was reduced | An answer that silently omits part of its normal work misleads the reader | MUST | OBJ-2 · CISO | VT-2 | DQ-D |
| FUN-004 | Submitting the same request again after a capacity refusal is safe and never duplicates work or side effects | Retries must not corrupt state or multiply downstream cost | MUST | OBJ-3 · Platform Engineering | VT-3 | DQ-E |

## Load and overload behaviour

| ID | Requirement | Rationale | Priority | Source | Validation theme | Related questions |
|---|---|---|---|---|---|---|
| LOD-001 | **INVARIANT.** Shedding, degrading, retrying or recovering never serves content that has not passed the Episode 02 eligibility check and the Episode 03 currency check | Load must never buy correctness shortcuts | MUST | OBJ-2 · CISO · CON-001 | VT-4, VT-6 | DQ-D, DQ-B |
| LOD-002 | **INVARIANT.** A request that will not be served is refused explicitly within the refusal deadline; no request is abandoned by silent timeout | An explicit refusal is actionable; a timeout is not (RSK-03) | MUST | OBJ-3 · Depot technicians | VT-2 | DQ-C, DQ-D |
| LOD-003 | The system states a capacity — a request rate and a concurrency — at which the promise holds, and the promise is expressed at the tail (p95), not the average | A promise about averages is not a promise (TP-3) | MUST | OBJ-1 · Platform Engineering | VT-1 | DQ-A |
| LOD-004 | Demand beyond the admitted capacity is handled by a stated rule — admit, queue within a bounded age, shed, or degrade — never by unbounded queueing | Unbounded queues convert overload into useless latency (RSK-03) | MUST | OBJ-1 · OBJ-3 | VT-2 | DQ-B, DQ-C |
| LOD-005 | Queued work that can no longer meet the promise is discarded before it is executed, not after | Spending scarce capacity on abandoned requests deepens the overload | MUST | OBJ-1 | VT-2 | DQ-C |
| LOD-006 | The architecture bounds the load it can place on the model service and on the records system, and never exceeds their quotas as a matter of course | Downstream limits are hard (TP-6, TP-15, RR-13) | MUST | Episode 01 RR-13 · CON-002 · Platform Engineering | VT-4 | DQ-B, DQ-F |
| LOD-007 | Retry behaviour is bounded by the architecture — a retry budget, backoff and jitter, and honoured retry guidance — so that retries cannot multiply offered load | Retry amplification was the incident's turning point (RSK-01) | MUST | OBJ-3 | VT-3 | DQ-E |
| LOD-008 | Overload in one depot, workload or client does not consume the capacity of the others | One bulletin campaign must not deny every other depot (RSK-04, TP-17) | MUST | OBJ-1 · Depot Maintenance Managers | VT-2 | DQ-C |
| LOD-009 | What may be degraded is defined in advance, ordered, and constrained so that no degradation step weakens LOD-001 | Degradation invented during an incident is untestable (RSK-06) | MUST | OBJ-2 · CISO | VT-2, VT-6 | DQ-D |
| LOD-010 | Saturation is distinguishable from failure in the system's own signals and in the responses it returns | "Too busy" and "broken" require different responses (RSK-05) | MUST | OBJ-6 · Platform Engineering | VT-7 | DQ-G |

## Freshness coexistence

| ID | Requirement | Rationale | Priority | Source | Validation theme | Related questions |
|---|---|---|---|---|---|---|
| FRS-C-001 | Answering and change processing each have a guaranteed floor; neither can be starved to zero by the other | Both are load-bearing promises from earlier episodes (RSK-04) | MUST | OBJ-4 · Records Manager | VT-5 | DQ-F |
| FRS-C-002 | When change processing is deliberately slowed to protect answering, the Episode 03 freshness position degrades **visibly**: the watermark stalls, the lag is reported and the breach alerts | A silent freshness loss would undo Episode 03's central claim | MUST | OBJ-4 · Records Manager · CON-001 | VT-5 | DQ-F |
| FRS-C-003 | Requests that cannot confirm currency because the authority is saturated are treated as the Episode 03 architecture already requires: withheld, and counted as a distinct, observable outcome | The incident's refusals must be visible as a capacity problem, not a content problem | MUST | OBJ-2 · OBJ-6 | VT-4, VT-5 | DQ-B, DQ-G |

## Security

| ID | Requirement | Rationale | Priority | Source | Validation theme | Related questions |
|---|---|---|---|---|---|---|
| SEC-001 | **INVARIANT.** The Episode 02 eligibility decision is made per request from current grants under every load condition; no cache, queue, batch or degradation reuses another user's decision or result | The authorisation boundary is absolute | MUST | CISO · CON-001 | VT-6 | DQ-D |
| SEC-002 | Capacity signals, refusals and queue metadata reveal nothing about restricted content or another user's activity | Overload responses must not become a side channel | MUST | CISO | VT-6 | DQ-D, DQ-G |
| SEC-003 | The architecture records where abuse and hostile traffic controls would belong, without implementing them, so the boundary inherited from Episode 02 stays explicit | TS-E02-08 was deferred here; the boundary must not silently disappear | SHOULD | Episode 02 TS-E02-08 | review | DQ-A |

## Data

| ID | Requirement | Rationale | Priority | Source | Validation theme | Related questions |
|---|---|---|---|---|---|---|
| DATA-001 | Anything retained to relieve load — cached retrieval results, embeddings, prepared prompts, queued requests — carries the eligibility scope and currency basis it was created under, and is unusable outside it | A cache is a derived copy; Episodes 02 and 03 already rule how derived copies behave | MUST | CISO · Records Manager | VT-6 | DQ-D |
| DATA-002 | Queued or shed requests hold no more user content than is needed to serve or refuse them, and are discarded on a bounded schedule | A queue is a store of user questions | MUST | CISO · DPO position (ASM-010) | review | DQ-C |

## Non-functional

| ID | Requirement | Rationale | Priority | Source | Validation theme | Related questions |
|---|---|---|---|---|---|---|
| NFR-001 | At the assumed daily peak (ASM-003), admitted requests meet the stated promise | The promise must hold where it matters | MUST | OBJ-1 | VT-1 | DQ-A |
| NFR-002 | At the assumed bulletin-burst peak (ASM-004), the system's behaviour matches its stated overload rule, with no invariant violated | The burst is the designed-for stress case | MUST | OBJ-1 · OBJ-2 | VT-2 | DQ-B, DQ-C |
| NFR-003 | After demand returns below capacity, normal service resumes within a bounded time, without manual intervention | Recovery must not outlast the incident (RSK-07) | MUST | OBJ-5 | VT-8 | DQ-H |
| NFR-004 | Refusal is fast: a capacity refusal costs materially less than an answer | Cheap refusals are what keep a system alive under overload | SHOULD | OBJ-1 | VT-2 | DQ-C |

## Operational

| ID | Requirement | Rationale | Priority | Source | Validation theme | Related questions |
|---|---|---|---|---|---|---|
| OPS-001 | Capacity, headroom, queue age, shed rate, degradation state and downstream throttling are observable in near real time | You cannot operate a promise you cannot see (OBJ-6) | MUST | Platform Engineering | VT-7 | DQ-G |
| OPS-002 | Sustained overload, an exhausted downstream quota, a stalled freshness watermark and a failed recovery each raise a distinct alert | Different causes need different responses | MUST | Platform Engineering · Records Manager | VT-7 | DQ-G |
| OPS-003 | Operators can change the admitted capacity and the degradation posture without a redeployment, within bounds that cannot disable an invariant | Incidents need a lever that is not a code change — and not a way to switch off safety | SHOULD | Platform Engineering · CISO | VT-6 | DQ-C, DQ-D |
| OPS-004 | The evidence for a capacity claim is reproducible: the same load profile, the same measurement method, a recorded result | A capacity number without a method is a rumour | MUST | OBJ-6 · OBJ-1 | VT-1 | DQ-A, DQ-G |

## Compliance — Kestrelmoor policy positions

| ID | Requirement | Rationale | Priority | Source | Validation theme | Related questions |
|---|---|---|---|---|---|---|
| CMP-001 | Kestrelmoor's safety policy position: a refusal is always acceptable; a stale or unauthorised answer never is, at any load | The company's stated order of preference, and the reason the incident was survivable | MUST | Head of Engineering Safety · CISO | VT-4, VT-6 | DQ-D |
| CMP-002 | Availability commitments made to depots are recorded with their measurement method and reviewed after each incident | A promise nobody measures is not a commitment | SHOULD | COO · Platform Engineering | review | DQ-A, DQ-G |
