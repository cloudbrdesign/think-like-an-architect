# Threat and Failure Model — Kestrelmoor Knowledge Assistant: answering under production traffic

**Status:** **APPROVED and FROZEN** (2026-09-20).

**Scope.** This episode's danger is mostly **legitimate load**, not attack. The model therefore leads with failure modes
and treats malicious traffic as one section among many (ASM-009: traffic is signed-in staff usage; abuse defence is a
recorded boundary, TS-E02-08). Nothing here is invented to fill a template: every entry traces to the incident, a
recorded risk, an assumption, or an inherited item from Episodes 01–03.

**What is preserved, not re-modelled:** the Episode 02 authorisation threat model and the Episode 03 freshness model
stand. This document adds only what capacity introduces — and its first question about any new mechanism is always
"can this weaken trust?"

## 1. Failure modes

| ID | Failure mode | How it arises | Consequence | Mitigation (proposed) | Residual |
|---|---|---|---|---|---|
| **FM-01** | Legitimate burst exceeds capacity | Shift start across eleven depots; bulletin doubles topic traffic (ASM-003, ASM-004) | Demand above permits | Admission control with typed refusal (ADR-001, ADR-002); age-bounded buffer for the short spike | Some users are refused at the peak — an accepted, visible cost |
| **FM-02** | Retry amplification | Refusals or slowness cause clients or users to resubmit; retries synchronise | Offered load multiplies; a survivable burst becomes an outage (RSK-01) | Server-issued jittered guidance, server-enforced budget, attempt identity, single flight (ADR-006) | A non-first-party client could still misbehave (ASM-008) |
| **FM-03** | Unbounded queue growth | Work admitted faster than it completes, with no age bound | Latency collapse; capacity spent on abandoned work (RSK-03) | Buffer bounded by age; pre-execution expiry; queue age as lead signal (ADR-002, ADR-007) | Age bounds depend on a correct duration model (ASM-005) |
| **FM-04** | Downstream quota exhaustion | Our own calls exceed model-service or records-system quotas (ASM-006, ASM-007; Episode 01 RR-13) | Rejections mistaken for failure; cascading retries | Permit budget per dependency, adaptive reduction, saturation classified distinctly (ADR-005, ADR-007) | Quota changes outside our control require re-sizing |
| **FM-05** | Workload starvation, either direction | Answering and change processing compete for one budget | Either the assistant stalls, or the Episode 03 currency claim lapses (RSK-04) | Floors for both, elastic middle, visible freshness degradation (ADR-003) | Idle reserved capacity; allocation must be reviewed |
| **FM-06** | Silent freshness loss | Change processing slowed to protect answering, without saying so | Answers current by luck; Episode 03's claim quietly untrue | Watermark stalls visibly; lag reported; distinct alert (ADR-003, ADR-007) | Operators must act on the alert |
| **FM-07** | Slow dependency mistaken for saturation | A dependency degrades in latency without rejecting | Adaptive limits throttle us for the wrong reason; self-inflicted overload | Separate latency and rejection signals; damping and floors on the adaptive reducer (ADR-005, ADR-007) | Controller misbehaviour remains possible; bounded by floors |
| **FM-08** | Partial recovery / thundering herd | Everyone returns at the same instant; caches cold; backlog stale | The incident repeats at 07:20 (RSK-07) | Staged ramp, hysteresis, staggered guidance, age-based backlog disposal (ADR-008) | Full capacity returns later than technically possible |
| **FM-09** | Capacity discovered only in production | No stated promise, no measured method | Nobody can plan a rollout or a campaign (RSK-08) | Stated capacity with recorded measurement method (ADR-001, OPS-004) | Numbers age as the system changes; re-measure on change |
| **FM-10** | Overload response becomes a side channel | Refusals, queue positions or timing differ by content sensitivity | Leakage of the existence or classification of content | Uniform refusal vocabulary and timing; no content-derived metadata in capacity responses (SEC-002) | Timing differences from real work remain possible; bounded by uniform refusals |

## 2. The trust-weakening threat (the one that matters most)

| ID | Threat | Why it is tempting | Control |
|---|---|---|---|
| **TT-01** | A degradation step serves content without the eligibility or currency check | It is the cheapest way to "fix" an overload | **Structural:** the trust path is on the single route every answer takes; the ladder controls only what happens around it (ADR-004). Proved by **FX-3**, which breaks it deliberately |
| **TT-02** | A cache or buffer reuses a result across users, or across a currency boundary | Caching looks like free capacity | Any retained artefact carries its eligibility scope and currency basis and is unusable outside it (DATA-001); coalescing is per user (ADR-006) |
| **TT-03** | An operator "turns off" a check during an incident | Pressure to restore service | Operator levers can change capacity and degradation posture, never disable an invariant (OPS-003) |
| **TT-04** | Saturation converts an unanswerable request into an answerable one | The failure a recorded decision names explicitly | Capacity may only subtract. Withheld stays withheld; refusal is not an answer (ADR-004, FRS-C-003) |

## 3. Malicious and abusive traffic (boundary, not design)

In scope to *name*, out of scope to *solve* (ASM-009, SEC-003; inherited TS-E02-08 from Episode 02).

| ID | Threat | Position |
|---|---|---|
| **MT-01** | Signed-in staff member floods the assistant, deliberately or by scripting | Partially mitigated by fair share and retry budgets (ADR-003, ADR-006): the blast radius is that person's share |
| **MT-02** | Credential-holding attacker drives load to deny service to others | Same mitigations; detection and response belong to abuse controls, which this engagement does not design |
| **MT-03** | Unauthenticated flood at the edge | Out of scope: no WAF, no rate-based abuse rules, no bot management here. Recorded as the standing boundary from Episode 02 |
| **MT-04** | Expensive-question crafting (maximising cost per request) | Named: cost-aware admission is a candidate in DQ-C but is not decided; bounded generation budgets limit the worst case |

**No threat was manufactured to fill this section**, and no security control is claimed that the engagement does not
build.

## 4. What the model tells the architecture

1. The dangerous cases are ordinary: a bulletin, a shift start, and users pressing a button again.
2. Every new capacity mechanism is a candidate trust-weakening path, so each one is checked against TT-01…TT-04.
3. Two failure modes are invisible without deliberate signals (FM-06 silent freshness loss, FM-10 side channel), so both
   get explicit checks rather than trust in inspection.
4. Recovery is a design surface, not an afterthought (FM-08).
