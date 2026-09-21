# Cost and Cleanup (E3) — Kestrelmoor Episode 04 lab

**Status:** DRAFT — build authorisation design (2026-09-20). Cleanup is designed **before** build authorisation, as
required.

## 1. Cost model (what actually drives spend)

The lab is deliberately tiny (demonstration parameters, not production values). Cost comes from:

| Driver | Where it arises | Lab-scale magnitude per full A–I session |
|---|---|---|
| **Model tokens** | Generation in scenario A, F, G; every admitted answer | Dominant driver. Bounded by short prompts, a capped generation budget, and only a few hundred admitted answers |
| Function invocations + duration | Every admitted or refused request, plus change processing | Hundreds of invocations, ~4 s each at small memory |
| Queue requests | Buffer sends/receives/deletes (64 KB chunks billed as one request each) | Low thousands |
| API requests | Caller entry point | Hundreds |
| Metrics, alarms, logs | Signals and evidence | ~10 custom metrics, 4 alarms, small log volume |

## 2. Dated pricing check (2026-09-20)

| Item | Finding | State |
|---|---|---|
| Lambda (US East, N. Virginia) | **$0.20 per 1M requests**; **$0.0000166667 per GB-second** (x86); free tier 1M requests and 400,000 GB-seconds per month | **VERIFIED** — *AWS Lambda pricing*, read 2026-09-20 |
| SQS | Free tier: **1M requests free per month**; billing unit: "each 64 KB chunk of a payload is billed as 1 request" | **PARTIALLY VERIFIED** — the per-million rate table did not render in the fetched page; confirm at build time |
| Model tokens | Per-model token pricing | **NOT VERIFIED** — must be confirmed for the exact model and region before build |
| API Gateway, CloudWatch metrics/alarms/logs | Request and metric pricing | **NOT VERIFIED** — confirm at build time |

**Estimate:** at these volumes the compute, queue and API components sit within or near the free tier, and the
meaningful spend is **model tokens**, which cannot be estimated responsibly until the per-model rate is verified.
**No total figure is claimed at this gate.** A bounded estimate is produced at build authorisation once the three
unverified rows are resolved.

**A low previous AWS bill proves nothing about this lab.** Episode 03 recorded exactly this trap: Cost Explorer lags,
and an unchanged month-to-date figure is not evidence that a run was free.

## 3. Cleanup design

| Step | Mechanism | Proof |
|---|---|---|
| 1. Tear down the stack | `lab-down traffic` (and `traffic-nobuffer` if created) — deletes every resource created by `lab-up` | Stack absent from `describe-stacks` |
| 2. Delete log groups explicitly | Log groups outlive stacks when created by invocation; the command deletes them by prefix | `logs describe-log-groups --log-group-name-prefix tla-s01e04` returns none |
| 3. Independent scan | A scan by episode prefix across functions, queues, APIs, alarms, metrics, roles and tagged resources — not merely "the stack is gone" | Recorded scan output: **CLEAN** |
| 4. Confirm no provisioned model throughput | Explicit check that only on-demand model access was used | Listing shows none |
| 5. Idempotent re-run | `lab-down` runs cleanly a second time | Exit 0, no changes |

**Cleanup is part of every scenario script's exit path**, and the learner README ends each part with it. The lab
creates nothing outside its own stack, which is what makes step 3 a complete proof rather than a hopeful one.

## 4. Cost guardrails
- A budget with alerts must exist before the first `lab-up` (preflight refuses otherwise).
- The generation budget caps tokens per answer; the degradation ladder tightens it further under load.
- Every scenario is seconds to minutes, not hours; nothing is billed by the hour and nothing is left running.
- The learner guidance states plainly: **run `lab-down` for each part, in the same session.**
