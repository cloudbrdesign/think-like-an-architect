# Control Catalogue (E3) — Kestrelmoor: answering under production traffic

**Status:** design, 2026-09-20.

Every accepted ADR maps to the **smallest** control that enforces it. A control with no observable signal or no
validation activity does not belong here.

| ID | Control | Architectural purpose (ADR) | Failure it prevents | Implementation mechanism | Observable signal | Validation | Cleanup responsibility |
|---|---|---|---|---|---|---|---|
| **CTL-401** | Partition permits | Bound admitted concurrency per workload (ADR-001, 003) | Unbounded admission; one workload consuming all capacity (FM-05) | Reserved concurrency per function + in-process permit counter | `concurrency_in_use` / `permits` per partition | TST-401, TST-405 | Function deleted with the stack |
| **CTL-402** | Fair-share allocation | One fairness domain cannot consume the capacity needed by all others (ADR-003) | A single depot denying the rest (FM-01, LOD-008) | Per-domain sub-permits inside the answering partition; domain = depot for this scenario, configurable | `refused_by_domain`, `concurrency_by_domain` | TST-402 | — |
| **CTL-403** | Age-bounded buffer | Absorb a short known burst only (ADR-002) | Overload hidden in a growing queue (FM-03) | Queue message carries a deadline; consumer discards expired **before** execution | `buffer_depth`, `buffer_age_seconds`, `expired_before_execution` | TST-403, FX-1 | Queue deleted with the stack; messages expire by retention |
| **CTL-404** | Explicit outcome classifier | Four never-merged caller outcomes (ADR-001) | CAPACITY_REFUSED and TRUST_WITHHELD collapsing into one error (the incident's ambiguity) | Single response constructor; outcome enum; no default branch | Counters per outcome | **TST-404** | — |
| **CTL-405** | Trust path enforcement | Degrade capability, not trust (ADR-004) | A rung, flag or operator action bypassing eligibility/currency (TT-01…TT-04) | Answers emitted only by the function that runs eligibility → currency → citation; degradation switches parameterise the answer path only | `trust_checks_run` = answers emitted; withheld counter | TST-404, **FX-3** | — |
| **CTL-406** | Degradation ladder | Ordered, mechanically constrained capability reduction (ADR-004) | Ad-hoc degradation invented under pressure (FM-06, RSK-06) | Single `degradation_level` computed from signals; feature switches keyed only to answer-path features | `degradation_level` + reason | TST-406 | — |
| **CTL-407** | Retry budget and guidance | Retries bounded by the architecture (ADR-006) | Retry amplification (FM-02) | Jittered retry-after issued on refusal; server-side budget per identity; attempt identity; single flight per user | `retries_accepted`, `retry_budget_exhausted`, `coalesced` | TST-407, **FX-2** | — |
| **CTL-408** | Downstream permits + adaptive reduction | Never oversubscribe a boundary we do not control (ADR-005) | Quota exhaustion presenting as failure (FM-04, FM-07) | Permit counter and token budget around model calls; reduce on throttling, restore gradually | `downstream_permits_in_use`, `downstream_rejections`, `adaptive_limit` | TST-408 | — |
| **CTL-409** | Freshness floor + visible degradation | Neither workload starves; falling freshness is observable (ADR-003) | Silent freshness loss (FM-06) | Reserved concurrency floor for change processing; watermark and lag emitted | `freshness_lag_seconds`, `watermark_stalled` | TST-405 | — |
| **CTL-410** | Saturation signals and alerts | See saturation before users do (ADR-007) | Operators learning from users (FM-09) | Custom metrics + queue age; four distinct alarms | Four alarm states | TST-410 | Alarms deleted with the stack |
| **CTL-411** | Bounded recovery | Recovery is part of the architecture (ADR-008) | Recovery outlasting the incident; stampede (FM-08) | Age-based backlog disposal; staged permit ramp; hysteresis; staggered retry-after | `recovery_state`, `permits_current`, time-to-normal | TST-411 | — |
| **CTL-412** | Demonstration parameters in one place | Teachability; cheap reproduction | Hidden magic numbers; expensive experiments | One config file, labelled *demonstration parameters* | Config echoed in every run summary | All tests read it | — |

**Cleanup principle:** every control lives inside the single lab stack or inside the learner's local generator. Nothing
persists outside the stack, so `lab-down` plus an independent scan is sufficient (see `COST_AND_CLEANUP.md`).
