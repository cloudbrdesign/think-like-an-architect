<!-- template: tla-architecture-brief/1 -->
# Architecture Brief — Kestrelmoor Knowledge Assistant: answering under production traffic

> Fictional scenario for learning. Kestrelmoor Rail Systems, its people, depots, procedures and documents are invented.
> All engagement data is synthetic.

**Status:** **APPROVED and FROZEN** (2026-09-20). Architecture engagement definition only: no options,
decisions, implementation or service selection at this gate. Not polished further after approval.

## 1. Client scenario

**Who they are.** Kestrelmoor Rail Systems designs, installs and maintains railway signalling and train-control
equipment for urban transit operators (about 2,400 employees, eleven maintenance depots). *Client continuity ruled by
the product owner (2026-09-20): Episode 04 is the direct consequence of Episodes 02 and 03, inside one system the learner already
knows.*

**Where they are now.** Two engagements have made the assistant's answers trustworthy:
- **Episode 02** made them *authorised*: per-section eligibility from current grants and the owner's classification,
  enforced inside the search and re-checked against the current record before generation.
- **Episode 03** made them *current*: the records system is the authority, the index is a derived copy, every request
  confirms currency against authority, and reconciliation proves nothing is missing and repairs what is.

Both properties cost work **on every request** and **continuously in the background**. That was acceptable in a pilot.

**What changed.** The assistant is now correct enough to roll out company-wide, so Kestrelmoor did exactly that. Every
depot, every shift, all 2,400 staff. The pilot's polite traffic became production traffic.

**What they want now.** An assistant that behaves predictably when everyone asks at once — that keeps its promises about
correctness and currency, and, when demand exceeds what it can serve, fails in a way the business chose in advance
rather than in whatever way the platform happens to fail.

## 2. Business problem

**Correct and current is not the same as available.** The Episode 02 and Episode 03 architecture answers every request
by doing real work: eligibility from current grants, a currency check against authority, retrieval, then generation
through a model service with its own capacity. Meanwhile reconciliation, re-indexing and repair run continuously. At
pilot volume these never collided. At company scale they do, and at exactly the worst moment — a safety bulletin is the
event that both floods the change pipeline and makes everyone ask the same question.

**Nobody can say what the assistant promises under load.** Today there is no stated capacity, no agreed behaviour at
overload, and no defined degradation. When the system is saturated the outcome is decided by timeouts, platform quotas
and client retries — none of which anyone chose.

**The morning that stopped the rollout (pilot-to-production review, synthetic).**

| Time | What happened |
|---|---|
| 06:50 | Engineering Safety issues a bulletin withdrawing a points-machine procedure and publishing its replacement. Change processing starts: about 50 procedures superseded, reconciliation running |
| 07:00 | Shift start across eleven depots. Technicians open the assistant at once; many ask about the bulletin. Request rate rises to roughly 12× the daily average within four minutes |
| 07:03 | Answers slow from about 4 s to over 40 s. The interface offers no feedback beyond a spinner |
| 07:05 | Technicians press ask again, and again. Each retry is a new request; the queue grows faster than it drains |
| 07:07 | The model service begins rejecting calls: its request-rate quota is exhausted. Authority look-ups for the currency check also slow, because change processing is hammering the same records system |
| 07:09 | The assistant starts refusing: it cannot confirm currency, so under the Episode 03 rule it withholds. Users see "can't answer" for a procedure that is on screen in the records system |
| 07:20 | Change processing finishes. Traffic is still heavy; the backlog of queued and retried requests takes another eleven minutes to drain |
| 07:31 | Normal service. No data was wrong, nothing leaked, and no answer was stale — but for half an hour, at shift start, the assistant was useless, and two depots have stopped using it |

**Why this is an architecture problem, not a scaling exercise.** Every safety property the last two engagements bought
is still intact — that is precisely why the system refused. The open questions are architectural: what does this API
promise, to whom, and at what rate? When demand exceeds capacity, what is shed and what is protected? What may degrade
without breaking the correctness and currency invariants? How do clients retry without amplifying the overload? And how
does the freshness work that Episode 03 made mandatory share a finite system with the answering it exists to serve?

## 3. Objectives

| ID | Objective |
|---|---|
| OBJ-1 | State what the assistant promises under load — a defined capacity and a defined behaviour beyond it — and hold that promise at the assumed peak |
| OBJ-2 | Preserve the Episode 02 authorisation and Episode 03 currency invariants under overload, including while shedding or degrading |
| OBJ-3 | Make overload behaviour explicit and honest to the caller, so clients can respond correctly instead of amplifying it |
| OBJ-4 | Keep answering and freshness work coexisting: neither starves the other, and the trade-off is visible and chosen |
| OBJ-5 | Recover to normal service without manual intervention once demand falls, in a bounded time |
| OBJ-6 | See saturation before users do: capacity, headroom and overload are observable and alertable |

## 4. Stakeholders

| Stakeholder | What they need | What they fear |
|---|---|---|
| Depot technicians | An answer at shift start, or a clear "not now, try in N seconds" | A spinner, then nothing; being stranded mid-job |
| Depot Maintenance Managers | Predictable availability at known peaks | Shifts that start late because the assistant stalled |
| Head of Engineering Safety | Safety bulletins reach staff fastest at exactly the busiest moment | The bulletin burst being the thing that breaks answering |
| Records Manager | Change processing keeps its freshness windows | Answering traffic starving reconciliation, so currency claims lapse |
| Platform Engineering | Bounded, observable resource use inside platform quotas | Retry storms; silent queue growth; recovery that needs a human |
| CISO | No relaxation of eligibility or currency checks under pressure | "Fast path" shortcuts that bypass a check when the system is busy |
| COO | Company-wide rollout that holds | Depots abandoning the tool after one bad morning |

## 5. Current state → target state

| | Current | Target |
|---|---|---|
| Capacity | Unstated; discovered during an incident | Stated, measured and monitored, with headroom defined |
| Overload behaviour | Emergent: timeouts, platform throttling, refusals | Chosen: admitted, shed or degraded by an explicit rule |
| Caller experience at overload | A spinner, then an error | An explicit, typed response the client can act on |
| Retries | Unbounded, client-decided, amplifying | Bounded and coordinated, so retries cannot multiply load |
| Freshness vs answering | Compete silently for the same resources | Share deliberately; the trade-off is chosen and visible |
| Correctness under load | Preserved by accident of refusal | Preserved by design, including while degraded |
| Recovery | Drains eventually; no defined time | Bounded, automatic and observed |

## 6. Requirements that drive the architecture

Full set: [`../02-requirements/REQUIREMENTS.md`](../02-requirements/REQUIREMENTS.md). The ones that shape everything:

- **LOD-001 (INVARIANT):** shedding or degrading never serves content that fails the eligibility or currency checks.
  Overload may reduce what is answered, never what is verified.
- **LOD-002 (INVARIANT):** a request that is not served is refused explicitly and promptly, with a typed reason and
  retry guidance — never a silent timeout.
- **LOD-004:** the system defines an admitted capacity, and demand beyond it is handled by a stated rule rather than by
  unbounded queueing.
- **LOD-007:** client retry behaviour is bounded by the architecture, not by client goodwill.
- **FRS-C-001:** answering and change processing each have a floor: neither can be starved to zero by the other, and
  whichever is degraded is visible.
- **AVL-002:** recovery to normal service is automatic and bounded after demand returns to normal.

## 7. Scale and traffic assumptions

Stated as assumptions with rationale in
[`../02-requirements/ASSUMPTIONS_AND_CONSTRAINTS.md`](../02-requirements/ASSUMPTIONS_AND_CONSTRAINTS.md)
(ASM-001 … ASM-011). No invented number is presented as fact. These values belong to this fictional engagement and
exist to force architectural trade-offs; they are not benchmarks, industry figures or platform limits.

## 8. Constraints

See [`../02-requirements/ASSUMPTIONS_AND_CONSTRAINTS.md`](../02-requirements/ASSUMPTIONS_AND_CONSTRAINTS.md)
(CON-001 … CON-008). In short:
- **Baselines stay:** the Episode 02 authorisation model and the Episode 03 currency and reconciliation architecture are
  preserved; their invariants are not relaxed to gain throughput.
- **Finite downstream capacity:** the model service and the records system both enforce their own limits; the
  architecture cannot assume they scale on demand.
- **Round-the-clock answering:** there is no maintenance window; peaks are daily and predictable in shape, not in size.
- **Delivery:** the same six-engineer team; no new manual steps for document owners or depot staff.

## 9. Risks

| ID | Risk | Why it matters |
|---|---|---|
| RSK-01 | Retry amplification turns a busy minute into an outage | The incident above; clients multiply load exactly when it is highest |
| RSK-02 | A "fast path" under load bypasses an eligibility or currency check | Would silently undo Episodes 02 and 03 |
| RSK-03 | Unbounded queueing converts an overload into a long, useless wait | Answers arrive after the user has given up; work is spent on abandoned requests |
| RSK-04 | Change processing starves answering, or answering starves change processing | Either the assistant stalls, or its currency claim quietly lapses |
| RSK-05 | Downstream quota exhaustion presents as a generic error | The system cannot distinguish "too busy" from "broken", so it cannot respond correctly |
| RSK-06 | Degradation is invented ad hoc during an incident | Undefined behaviour is unsafe and untestable |
| RSK-07 | Recovery is slower than the incident: cold caches, backlog, thundering herd | The outage outlives the burst that caused it |
| RSK-08 | Capacity is only discovered in production | Nobody can plan a rollout or a bulletin campaign |

## 10. Deliverables

At this gate (E1): this brief, the requirement set, assumptions and constraints, architecture decision questions, and
proposed validation themes. Nothing else.

Later gates, only when authorised: options analysis and ADRs, target architecture and threat model, build authorisation,
the educational implementation with its evidence, the learner lab and its publication, then the media pipeline.

## 11. Teaching prerequisites

Episode 04 uses vocabulary that Episodes 01–03 did not need. Under the production model (no fixed runtime, concept-first
teaching), these are recorded now as **teaching requirements**, so the later script and storyboard can explain each one
before the architecture narrative leans on it. **The teaching sequence is not designed here, and no script is written at
this gate.**

| # | Concept | Plain English | Why it matters here | Explain on screen? | Misconception to prevent |
|---|---|---|---|---|---|
| TP-1 | Request rate | How many requests arrive per second or minute | The peak is defined in these terms; quotas are enforced in them | **Yes — first** | "Load" is not one number: rate and concurrency are different things |
| TP-2 | Concurrency | How many requests are in flight at the same time | A slow answer holds resources; concurrency, not rate, exhausts them | **Yes — first** | That a higher request rate always means more load; short fast calls and long slow ones differ |
| TP-3 | Latency (and percentiles) | How long one answer takes; p50 versus p95/p99 | The promise is about the slow tail, not the average | **Yes** | That an average latency describes the user experience |
| TP-4 | Throughput | How much work the system actually completes per unit time | Capacity is throughput at an acceptable latency, not the maximum possible | **Yes** | That throughput and rate are the same; arriving is not completing |
| TP-5 | Capacity and headroom | The demand the system can serve within its promise, and the margin kept spare | OBJ-1 needs a number that means something | **Yes** | That capacity is a hardware property rather than a promise-bounded property |
| TP-6 | Quotas | A hard limit imposed by a platform or service | The model service and records system both have them; they are not negotiable at runtime | **Yes** | That a quota is a performance setting you can tune away |
| TP-7 | Throttling | Refusing or slowing work once a limit is reached | Both what the platform does to us and what we may do to callers | **Yes** | That throttling is a failure; it is a designed response |
| TP-8 | Back-pressure | Telling the caller to slow down, instead of absorbing more than you can handle | The central idea of the episode's answer | **Yes — load-bearing** | That back-pressure means dropping work silently |
| TP-9 | Queueing and buffering | Holding requests until capacity frees up | Queues trade latency for smoothing; unbounded queues trade it away entirely | **Yes** | That a queue solves overload — it only relocates it |
| TP-10 | Queue age vs queue length | How long the oldest waiting item has waited, versus how many wait | Age is the signal that predicts broken promises | Yes, briefly | That length alone tells you whether you are in trouble |
| TP-11 | Load shedding | Deliberately refusing some work to protect the rest | The chosen alternative to universal slowness | **Yes — load-bearing** | That shedding is the same as failing; it is a choice about *whose* request is refused |
| TP-12 | Retry amplification | Retries multiplying load precisely when the system is weakest | The incident's turning point (RSK-01) | **Yes — load-bearing** | That retrying is always the polite, safe client behaviour |
| TP-13 | Backoff and jitter | Waiting longer between retries, with randomness so clients do not synchronise | The mechanical fix for TP-12 | Yes, briefly | That a fixed retry delay is enough; synchronised retries re-form the spike |
| TP-14 | Timeouts | Deciding when to stop waiting | A timeout without shedding just wastes capacity on abandoned work | Yes | That a long timeout is generous; it is often self-harm |
| TP-15 | Application capacity vs downstream capacity | Our own limits versus the model service's and the records system's | We can scale our part and still be bounded by theirs | **Yes — load-bearing** | That adding instances raises capacity when the constraint is downstream |
| TP-16 | Graceful degradation | Continuing with reduced function instead of failing entirely | What may be reduced is constrained by the Episode 02/03 invariants | **Yes** | That degrading means relaxing a correctness or eligibility check |
| TP-17 | Fairness and isolation | Preventing one depot, user or workload from consuming everything | Bulletin traffic from one depot must not deny every other depot | Yes | That "first come, first served" is fair under overload |
| TP-18 | Recovery and draining | Returning to normal after the spike, including the backlog | OBJ-5; recovery can outlast the incident (RSK-07) | Yes | That when load drops, service is instantly normal again |

## 12. Out of scope

- **Tenant isolation:** Episode 01.
- **The authorisation model:** Episode 02's model is the baseline; this engagement only requires that it holds under
  load.
- **Freshness, reconciliation and deletion:** Episode 03's architecture is the baseline; here it appears only as a
  competing workload and as an invariant to preserve.
- **Cost optimisation:** Episode 05 (cost is a constraint here, not an optimisation target).
- **Audit evidence and provenance at scale:** Episode 06.
- **Behaviour when the model service is unavailable** (as opposed to saturated): Episode 07.
- **Abuse, WAF and hostile denial of service:** named as a boundary. This engagement treats legitimate load, and
  records the security boundary Episode 02 deferred (TS-E02-08) without designing abuse controls.
- **Multi-region and disaster recovery:** not in Season 1's scope.
