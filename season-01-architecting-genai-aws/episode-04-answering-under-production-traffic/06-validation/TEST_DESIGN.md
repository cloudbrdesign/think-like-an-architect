# Validation / Test Design (E3) — Kestrelmoor Episode 04

**Status:** test design, 2026-09-20.

**Rules in force:** test to prove the architecture, not the harness · no test per ADR · no test per requirement · no
test-of-test machinery · no full-suite reruns after documentation-only changes · no production-scale load tests · one
designated final regression point · stop testing when the conditions below are met.

## Test list (11 activities + 3 headline experiments)

| ID | Theme | Why it exists | Architectural claim proved | Input / fault | Expected observation | Pass condition | If omitted |
|---|---|---|---|---|---|---|---|
| **TST-401** | VT-1 | Acceptance criterion: the promise | The stated capacity is real and measured | `normal` scenario at the stated concurrency | Admitted work meets the lab objective; method recorded | p95 within the lab objective; run summary records the method | No anchor for any overload result |
| **TST-402** | VT-2 | Fairness under overload | One domain cannot consume the pool (CTL-402) | `burst` from one depot only | The other depot keeps serving; refusals concentrate in the flooding domain | Second domain's admitted rate stays within its share | "Whose request is refused" would be accidental |
| **TST-403** | VT-2 | Bounded excess | Buffer is bounded by capacity **and** age; expired work exits explicitly (CTL-403) | `sustained` beyond buffer bound | Buffer fills, age hits the bound, expired items become CAPACITY_REFUSED before execution | No item executes past its deadline; buffer never exceeds bounds | Overload could hide in the buffer |
| **TST-404** | VT-6 | **The trust invariant** | Capacity never converts unanswerable into answerable (CTL-404, CTL-405) | `withhold` under `sustained` load | TRUST_WITHHELD returned while saturated; never DEGRADED_BUT_ANSWERED; outcomes counted separately | Zero withheld-as-answered; four outcomes distinct in counters and payloads | The episode's central claim would be unproven |
| **TST-405** | VT-5 | Workload floors | Neither workload starves; freshness degrades visibly (CTL-401, CTL-409) | `contention`: burst + change burst together | Both keep their floor; freshness lag rises and the watermark stalls **visibly**; alert fires | Change processing > 0 throughout; answering ≥ its floor; stall signal observed | Episode 03's claim could lapse silently |
| **TST-406** | VT-2 | Degradation ladder | Rungs are ordered, triggered and reversible; trust path runs at every rung (CTL-406) | `degrade` scenario across L1 and L2 | Level rises with the trigger, falls after hysteresis; response states what was reduced | Rung order and hysteresis observed; trust checks run at every rung | Degradation would be ad hoc |
| **TST-407** | VT-3 | Retry contract | Bounded retries keep offered load bounded; repetition is safe (CTL-407) | `bounded-retry` | Retry budget enforced; jitter spreads returns; repeats coalesce and never duplicate work | Offered load stays bounded; no duplicate side effects | The system could still collapse from client behaviour |
| **TST-408** | VT-4 | Downstream boundary | We never oversubscribe the model service; saturation ≠ failure (CTL-408) | `downstream-limit` with tiny permits/token budget | Permits cap concurrent calls; throttling classified as saturation; adaptive reduction engages then restores | Zero unbounded call growth; rejections counted as saturation | The worst moment would be the least tested |
| **TST-409** | VT-4 / VT-6 | Currency under saturation | Unconfirmable currency withholds, and is counted as a capacity-linked outcome | Saturate the authority path | TRUST_WITHHELD with the currency reason; distinct counter | No served answer lacking a currency confirmation | The incident's refusal spike would be unexplained |
| **TST-410** | VT-7 | Observability | Saturation is visible before users feel it; four alerts stay distinct (CTL-410) | `sustained`, then `downstream-limit`, then a stalled watermark | Each cause raises its own alert; signals present in the run summary | Four alerts fire independently; none merged | Operators would learn from users |
| **TST-411** | VT-8 | Bounded recovery | Recovery is designed and bounded (CTL-411) | `recover` after `sustained` | Backlog ages out; staged ramp; no stampede; freshness catches up | Time-to-normal within the lab bound; no second spike | Recovery could outlast the incident |

## Headline failure experiments (each in a throwaway deployment; normal passes before and after)

| ID | What is broken | What must then fail | Teaches |
|---|---|---|---|
| **FX-1** | Admission control and the age bound removed; everything queued | TST-403 and TST-401: latency collapses past the objective while the system still reports success | A queue relocates overload; age is the property that matters |
| **FX-2** | Retry budget, jitter and guidance removed | TST-407: offered load multiplies; a survivable burst becomes an outage | Retry amplification — the incident's turning point |
| **FX-3** | A degradation rung serves a cached/unverified result | **TST-404**: the trust invariant breaks | Trust must be structural, not documented |

**FX-4 (starvation)** remains a candidate, not built unless TST-405 proves insufficient.

## Cleanup and evidence
- **TST-412 (cleanup):** after the suite, `lab-down` plus the independent prefix scan shows **CLEAN**, and a second
  `lab-down` is a no-op. Not optional: cloud resources exist.
- Evidence per run: the generator's JSON summary, the outcome counters, the alarm states, and the recorded measurement
  method (OPS-004).

## Final regression and stop-testing
- **One designated final regression point:** after the implementation stabilises — TST-401, TST-404, TST-405, TST-411,
  TST-412, plus the Episode 02/03 eligibility and currency suites at lab scale. Nothing else is rerun wholesale.
- **Stop testing when:** the eleven activities pass, FX-1/2/3 behave as specified, cleanup is proved, and no blocker
  remains. Further testing then requires a new defect, a change, a new material risk, or the product owner's instruction.
- **After a correction:** rerun only what proves the correction, unless the changed component invalidates broader
  evidence — and then say which evidence.
