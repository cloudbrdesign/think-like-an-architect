# Episode 01 — How to Build Multi-Tenant RAG Without Leaking Customer Data

> **You are the architect. Here is the client problem.**

**Status: educational implementation (E4).** This folder contains:
- the approved engagement design;
- the **approved architecture**;
- the **educational implementation design**: platform verification, controls, harness design, cost and cleanup;
- the **educational implementation**: one CloudFormation stack, the application, the test harness, the sensitivity
  variant and the cleanup flow.

Reading costs nothing. **Deploying creates billable resources in your own sandbox account** — read
[Cost and cleanup](05-implementation/COST_AND_CLEANUP.md) before step 20.

The principle this episode is built around:

```
IDENTITY → AUTHORISATION → RETRIEVAL BOUNDARY
```

Tenant isolation must not depend on instructions given to a model. By the end of the engagement you must be able to show,
with tests that are allowed to fail, that one customer cannot retrieve another customer's information.

## Work through it in this order

### Engagement (approved)

| Step | Read / produce | File |
|---|---|---|
| 1 | Understand the client, the business problem and what failure costs | [Architecture Brief](01-business-context/ARCHITECTURE_BRIEF.md) |
| 2 | Study the requirements — especially the security invariants | [Requirements](02-requirements/REQUIREMENTS.md) |
| 3 | Separate what is assumed from what is constrained | [Assumptions and constraints](02-requirements/ASSUMPTIONS_AND_CONSTRAINTS.md) |
| 4 | See what can go wrong before choosing anything | [Initial risk register and threat-model inputs](03-architecture/INITIAL_RISK_REGISTER.md) |
| 5 | **Try to answer the decision questions yourself before step 6** | [Architecture decision questions](04-decisions/ARCHITECTURE_DECISION_QUESTIONS.md) |

### Architecture (approved)

| Step | Read / produce | File |
|---|---|---|
| 6 | Compare credible options against criteria derived from the requirements | [Architecture options analysis](04-decisions/ARCHITECTURE_OPTIONS_ANALYSIS.md) |
| 7 | Study each decision, including why the alternatives lost | [ADR-001 isolation model](04-decisions/ADR-001-tenant-isolation-model.md) · [ADR-002 tenant context](04-decisions/ADR-002-trusted-tenant-context.md) · [ADR-003 authorisation point](04-decisions/ADR-003-authorisation-enforcement-point.md) · [ADR-004 attribution](04-decisions/ADR-004-document-tenant-attribution.md) · [ADR-005 retrieval boundary](04-decisions/ADR-005-retrieval-boundary.md) · [ADR-006 audit](04-decisions/ADR-006-audit-and-observability.md) · [ADR-007 model boundary](04-decisions/ADR-007-model-invocation-boundary.md) |
| 8 | See the trust boundaries, flows, fail-closed behaviour and bypass analysis | [Target architecture](03-architecture/TARGET_ARCHITECTURE.md) · [diagrams](03-architecture/diagrams/) |
| 9 | Attack the design | [Threat model and red-team review](03-architecture/THREAT_MODEL.md) |
| 10 | Know what risk remains, and who owns it | [Residual risk register](03-architecture/RESIDUAL_RISK_REGISTER.md) |
| 11 | Understand cost structure and where the design stops fitting | [Cost and scale analysis](03-architecture/COST_AND_SCALE_ANALYSIS.md) |
| 12 | Only now: see how the patterns map to AWS, with dated sources | [AWS service mapping](03-architecture/AWS_SERVICE_MAPPING.md) |
| 13 | Know exactly how the architecture will be proven | [Validation plan](06-validation/VALIDATION_PLAN.md) · [Acceptance test intent](06-validation/ACCEPTANCE_TEST_INTENT.md) · [Traceability matrix](06-validation/TRACEABILITY_MATRIX.md) |
| 14 | Plan the record of your work | [Portfolio evidence plan](07-evidence/PORTFOLIO_EVIDENCE_PLAN.md) |
| 15 | Prepare to defend your design | [Architecture review questions](ARCHITECTURE_REVIEW_QUESTIONS.md) |

### Implementation design (E3)

| Step | Read / produce | File |
|---|---|---|
| 16 | See what has been proven about the platform — and what still needs an experiment | [Platform verification](05-implementation/PLATFORM_VERIFICATION.md) |
| 17 | See exactly what you will build, why each part exists, and where each control lives | [Implementation design](05-implementation/IMPLEMENTATION_DESIGN.md) · [Implementation controls](05-implementation/IMPLEMENTATION_CONTROLS.md) |
| 18 | Know how the isolation control will be proven, including the sensitivity variant | [Test harness design](06-validation/TEST_HARNESS_DESIGN.md) |
| 19 | Know the cost and the cleanup before deploying anything | [Cost and cleanup](05-implementation/COST_AND_CLEANUP.md) |

### Build, attack and prove it (E4)

| Step | Do | File |
|---|---|---|
| 20 | Find, in the source, where tenant authority comes from, where the filter is built and what prevents bypass — then deploy | [Build it](05-implementation/README.md) · [template](05-implementation/infrastructure/template.yaml) · [primary control](05-implementation/app/shared/retrieval_scope.py) |
| 21 | Load synthetic tenants, try to forge a tenant, and read the audit record | [Build it — explore the boundary](05-implementation/README.md#explore-the-boundary-yourself-between-steps-3-and-4) |
| 22 | Run the attack suite, then prove the tests fail when the primary control is removed | [Harness](06-validation/harness/) · [sensitivity variant](06-validation/sensitivity/retrieval_scope.py) |
| 23 | Clean up, verify, and keep your evidence | [Cost and cleanup](05-implementation/COST_AND_CLEANUP.md) · [Portfolio evidence plan](07-evidence/PORTFOLIO_EVIDENCE_PLAN.md) |

## Check the traceability chain

```
python3 tools/traceability_check.py season-01-architecting-genai-aws/episode-01-multi-tenant-rag
python3 tools/traceability_check.py season-01-architecting-genai-aws/episode-01-multi-tenant-rag --why ADR-001
python3 tools/traceability_check.py season-01-architecting-genai-aws/episode-01-multi-tenant-rag --proof SEC-001
```

## What this is not

Not a service tutorial. Not certification preparation. The evidence you produce is **portfolio evidence of the work you
performed** — it does not certify competence.
