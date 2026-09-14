# Episode 01 — How to Build Multi-Tenant RAG Without Leaking Customer Data

> **You are the architect. Here is the client problem.**

**Start here.** This folder is a complete architecture engagement. You take a realistic problem from business need to a
tested, defended architecture, then build it, attack it and prove the boundary holds.

```
IDENTITY → AUTHORISATION → RETRIEVAL BOUNDARY
```

Tenant isolation must be enforced **before retrieval**. The model is not the security boundary. By the end you will be
able to show — with tests that are allowed to fail — that one customer cannot retrieve another customer's information.

**Status:** educational implementation validated (E4). The engagement, the implementation, the validation suite and an
example evidence set are all here. Everything in this folder is free; no purchase is needed to complete the engagement.

## Before you start

| | |
|---|---|
| **What you need to read along** | Nothing but this repository |
| **What you need to build it** | A dedicated sandbox AWS account with administrator access, Python 3.10+ and `boto3`. Prerequisites and the preflight check are in the [learner guide](05-implementation/README.md#prerequisites) |
| **What it costs** | Reading costs nothing. **Deploying creates billable resources in your own account.** Read [Cost and cleanup](05-implementation/COST_AND_CLEANUP.md) first, and set a budget alert |
| **How long the lab takes** | CloudBrewery's own run from a fresh clone took about 18 minutes, from preflight to verified cleanup ([evidence](07-evidence/e4-validation-2026-09-14/FRESH_COPY_RUN.md)). Reading and reasoning time is yours |
| **What you keep** | [Portfolio evidence of the work you performed](07-evidence/PORTFOLIO_EVIDENCE_PLAN.md) — not a certification |

## The engagement in ten stages

Work through the stages in order. **Try to answer each stage's checkpoint yourself before reading the next stage** —
reasoning matters more than the answers in the files.

| Stage | What you do | Read / run | Checkpoint — you should be able to answer |
|---|---|---|---|
| **1 · Business problem** | Understand the client, the stakes and what failure costs | [Architecture Brief](01-business-context/ARCHITECTURE_BRIEF.md) | Why is one cross-customer leak fatal for this product? |
| **2 · Requirements** | Separate invariants from preferences, and assumptions from constraints | [Requirements](02-requirements/REQUIREMENTS.md) · [Assumptions and constraints](02-requirements/ASSUMPTIONS_AND_CONSTRAINTS.md) · [Initial risk register](03-architecture/INITIAL_RISK_REGISTER.md) | Which requirements can never bend, and why must authorisation happen before retrieval? |
| **3 · Options** | Answer the decision questions **yourself**, then compare credible options against criteria | [Decision questions](04-decisions/ARCHITECTURE_DECISION_QUESTIONS.md) · [Options analysis](04-decisions/ARCHITECTURE_OPTIONS_ANALYSIS.md) | Where can tenant isolation live — prompt, post-retrieval filter, per-tenant infrastructure or inside the search — and what does each cost? |
| **4 · Decisions** | Study each decision and why the alternatives lost | [ADR-001](04-decisions/ADR-001-tenant-isolation-model.md) · [ADR-002](04-decisions/ADR-002-trusted-tenant-context.md) · [ADR-003](04-decisions/ADR-003-authorisation-enforcement-point.md) · [ADR-004](04-decisions/ADR-004-document-tenant-attribution.md) · [ADR-005](04-decisions/ADR-005-retrieval-boundary.md) · [ADR-006](04-decisions/ADR-006-audit-and-observability.md) · [ADR-007](04-decisions/ADR-007-model-invocation-boundary.md) | Why is the tenant constraint evaluated inside every search, and what is the price of that choice? |
| **5 · Architecture** | See trust boundaries, flows, fail-closed behaviour, threats, residual risk, cost — and only then the AWS mapping | [Target architecture](03-architecture/TARGET_ARCHITECTURE.md) · [diagrams](03-architecture/diagrams/) · [Threat model](03-architecture/THREAT_MODEL.md) · [Residual risks](03-architecture/RESIDUAL_RISK_REGISTER.md) · [Cost and scale](03-architecture/COST_AND_SCALE_ANALYSIS.md) · [AWS service mapping](03-architecture/AWS_SERVICE_MAPPING.md) | Where does untrusted tenant input become trusted context? What breaks isolation on its own? |
| **6 · Build** | Check what the platform was proven to do, read where each control lives, then deploy | [Platform verification](05-implementation/PLATFORM_VERIFICATION.md) · [Implementation design](05-implementation/IMPLEMENTATION_DESIGN.md) · [Controls](05-implementation/IMPLEMENTATION_CONTROLS.md) · [**Learner guide** — steps 0 to 3](05-implementation/README.md) | Which single function builds the tenant filter, and what stops any other code from building a different one? |
| **7 · Attack** | Forge a tenant, attack the prompt, inspect the audit record | [Learner guide — explore the boundary](05-implementation/README.md#explore-the-boundary-yourself-between-steps-3-and-4) · [Validation plan](06-validation/VALIDATION_PLAN.md) | You sent `tenant-b` in four places. What did the audit record show as tenant context and constraint? |
| **8 · Validate** | Run the full suite, then prove the tests can fail with the sensitivity experiment | [Learner guide — steps 4 and 5](05-implementation/README.md#run-it--steps-0-to-6) · [Test harness design](06-validation/TEST_HARNESS_DESIGN.md) · [Traceability matrix](06-validation/TRACEABILITY_MATRIX.md) | How do you know your cross-tenant tests are not passing vacuously? |
| **9 · Evidence** | Keep your results, clean up, verify nothing remains | [Learner guide — step 6](05-implementation/README.md#run-it--steps-0-to-6) · [Portfolio evidence plan](07-evidence/PORTFOLIO_EVIDENCE_PLAN.md) · [example evidence set](07-evidence/e4-validation-2026-09-14/README.md) | What exactly did your run prove, under which conditions — and what did it not prove? |
| **10 · Architecture review** | Defend the architecture as you would to a review board | [Architecture review questions](ARCHITECTURE_REVIEW_QUESTIONS.md) | Could you answer every question by citing your own artifacts? |

## Check the traceability chain

Every requirement traces to its decision, control, implementing source, test and result:

```
python3 tools/traceability_check.py season-01-architecting-genai-aws/episode-01-multi-tenant-rag
python3 tools/traceability_check.py season-01-architecting-genai-aws/episode-01-multi-tenant-rag --why ADR-005
python3 tools/traceability_check.py season-01-architecting-genai-aws/episode-01-multi-tenant-rag --proof SEC-001
```

## What the example evidence shows — and its limits

CloudBrewery's run of this implementation, from a fresh clone, is in
[07-evidence/e4-validation-2026-09-14](07-evidence/e4-validation-2026-09-14/README.md):
- all 22 validation tests passed;
- the sensitivity experiment made the isolation tests fail once the primary control was removed;
- cleanup was verified.

The results hold for that educational deployment, account, region, corpus and set of conditions. They are not a proof of
production-scale isolation or performance. Your own run is your evidence.

## What this is not

Not a service tutorial. Not certification preparation. The evidence you produce is **portfolio evidence of the work you
performed** — it does not certify competence.
