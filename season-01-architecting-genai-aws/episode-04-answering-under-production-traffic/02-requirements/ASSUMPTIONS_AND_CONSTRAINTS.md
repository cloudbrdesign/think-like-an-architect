# Assumptions and Constraints — Kestrelmoor Knowledge Assistant: answering under production traffic

**Status:** **APPROVED and FROZEN** (2026-09-20). the numbers are **working architecture
assumptions** — design inputs for the engagement and the teaching lab, never claims about measured production traffic.
If later evidence invalidates one, return to the affected architecture decision rather than changing it silently.

An **assumption** is believed true but not confirmed. Each names what changes if it is false. A **constraint** is a
condition the architecture must work within, listed because it forces a trade-off.

Every number here is a working architecture assumption for this fictional engagement. None is a
benchmark, an industry figure or a platform limit.

## Assumptions

| ID | Assumption | Why it matters to the architecture | If false, then | Validate by |
|---|---|---|---|---|
| ASM-001 | About 2,400 staff across eleven depots after company-wide rollout; roughly 1,500 use the assistant in a given week (**ASSUMPTION**, carried from Episodes 02–03) | Sets the population that can arrive at once | Peak sizing changes | Pilot usage data; COO's rollout plan |
| ASM-002 | Daily traffic averages about 4,000 questions, spread unevenly across 24 hours (**ASSUMPTION**) | The baseline the peak multiplies | Capacity target changes | Pilot telemetry over 90 days |
| ASM-003 | Shift starts at 07:00, 15:00 and 23:00 produce the daily peaks; the 07:00 peak reaches about 12× the daily average request rate for four to six minutes, across all depots at once (**ASSUMPTION**) | This is the promise-defining case (NFR-001) | The stated capacity is wrong in either direction | Pilot telemetry; depot shift rosters |
| ASM-004 | A safety bulletin adds a burst on top of a shift start: roughly 50 procedures superseded and up to 20,000 documents touched by a reclassification campaign, while question traffic doubles again on the bulletin topic (**ASSUMPTION**, consistent with Episode 03 ASM-004) | The designed-for stress case (NFR-002) | Burst sizing is wrong | Head of Engineering Safety; Records Manager |
| ASM-005 | A normal answer takes about 4 s end to end at pilot load, most of it in retrieval and generation (**ASSUMPTION** — to be measured) | Concurrency, not rate, is what exhausts the system (TP-2) | The capacity model changes shape | Measurement in the educational implementation |
| ASM-006 | The model service enforces request-rate and token quotas per account and region, rejecting calls beyond them, and those quotas are not raisable within an incident (**ASSUMPTION**) | Downstream capacity is a hard bound (LOD-006) | Some pressure can be absorbed downstream; the architecture's job narrows | Platform verification at the architecture gate (dated, per the currency check) |
| ASM-007 | The records system serves the request-time currency checks and the change-processing reads from the same finite capacity (**ASSUMPTION**) | This is why answering and freshness contend (FRS-C-001) | The contention disappears and DQ-F simplifies | Records-system integration review |
| ASM-008 | Clients are Kestrelmoor's own web and mobile assistant apps; their retry behaviour can be changed by this engagement (**ASSUMPTION**) | LOD-007 depends on being able to bound retries at the source | Retry discipline must be enforced entirely server-side | Application team confirmation |
| ASM-009 | Traffic is legitimate staff usage behind company sign-in; hostile or automated abuse is out of scope for this engagement (**ASSUMPTION**) | Separates capacity design from abuse defence (SEC-003) | Abuse controls become a requirement, not a boundary | CISO; Episode 02 TS-E02-08 position |
| ASM-010 | Queued user questions are personal data under Kestrelmoor's policy and may not be retained beyond what serving them requires (**ASSUMPTION**; policy position owned by the DPO, not legal advice) | Bounds what a queue may hold (DATA-002) | Retention limits change | DPO confirms policy |
| ASM-011 | The learner implementation uses a synthetic organisation, synthetic people, synthetic documents and generated load only | No real personal data, secrets or customer information | — | Stated fact for the learner implementation |

## Constraints

| ID | Constraint | Consequence for the architecture |
|---|---|---|
| CON-001 | The Episode 02 authorisation model and the Episode 03 currency and reconciliation architecture are the baseline; their invariants may not be relaxed for throughput | Every capacity mechanism must be checked against both; "faster" is never a reason to skip a check |
| CON-002 | Downstream capacity (model service, records system) is finite and enforced by quotas the engagement does not control | The architecture must bound its own demand and behave correctly when refused |
| CON-003 | Answering runs 24 hours a day; there is no maintenance window, and peaks recur daily | Capacity changes and recovery must happen while serving |
| CON-004 | The same six-engineer team delivers this engagement alongside the existing system | Mechanisms must be few, testable and operable; complexity is a cost |
| CON-005 | No new manual steps for document owners or depot staff | Overload handling must be automatic and self-explanatory in the response |
| CON-006 | Cost is bounded: the platform spend for this engagement must stay within the existing envelope, and cost optimisation itself belongs to Episode 05 | Capacity cannot be bought without limit; the design must choose behaviour, not just size |
| CON-007 | The educational implementation must demonstrate overload at a small, cheap scale, with deliberately small quotas rather than real production volumes | Evidence must be reproducible on a sandbox account; no large-scale load testing |
| CON-008 | Public learner material carries synthetic data only, and no account identifiers, quota values from a real account, or internal governance vocabulary | Constrains what evidence can be published |
