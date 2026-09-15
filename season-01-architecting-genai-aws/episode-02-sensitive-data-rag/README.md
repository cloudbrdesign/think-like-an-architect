# Episode 02 — How to Design RAG When Your Documents Contain Sensitive Data

**Client:** Kestrelmoor Rail Systems (fictional). **Everything in this folder is synthetic.**

## The architecture problem

Episode 01 asked: *how do we stop one customer from retrieving another customer's documents?*

Episode 02 asks a different question. Inside a single organisation:
- every employee is authenticated;
- every document belongs to the company;
- yet the information inside those documents is not equally available to everyone.

**Central architecture question:** where is retrieval eligibility decided — from which authoritative inputs, and at what
granularity — so that information a legitimate employee is not entitled to never reaches generation?

**The invariant this engagement designs, builds and tests:**

> A section reaches generation only if its owner-assigned classification and scope, as currently recorded, match an
> entitlement the requester holds at the moment of the request — decided outside the model, enforced inside the
> search, re-checked before generation. Content that no use case needs is never indexed.

- **Authenticated is not authorised.**
- **Authorised for a document is not authorised for every section.**
- **The model is not the authorization authority. The prompt is not the authorization boundary.**
- **No authoritative current grants = no retrieval.**
- **The tier is not the authorization boundary.**

## Work through it in order

Try to answer each stage's questions before reading the next stage's answer.

| Stage | Artifact |
|---|---|
| 1 Business problem | [01-business-context/ARCHITECTURE_BRIEF.md](01-business-context/ARCHITECTURE_BRIEF.md) |
| 2 Requirements | [02-requirements/REQUIREMENTS.md](02-requirements/REQUIREMENTS.md) · [ASSUMPTIONS_AND_CONSTRAINTS.md](02-requirements/ASSUMPTIONS_AND_CONSTRAINTS.md) |
| 3 Identity, authorization and sensitivity | [03-architecture/AUTHORIZATION_AND_SENSITIVITY_MODEL.md](03-architecture/AUTHORIZATION_AND_SENSITIVITY_MODEL.md) |
| 4 Synthetic data | [03-architecture/SYNTHETIC_DATA_MODEL.md](03-architecture/SYNTHETIC_DATA_MODEL.md) |
| 5 Threats | [03-architecture/THREAT_MODEL.md](03-architecture/THREAT_MODEL.md) |
| 6 Decision questions — answer these yourself first | [04-decisions/ARCHITECTURE_DECISION_QUESTIONS.md](04-decisions/ARCHITECTURE_DECISION_QUESTIONS.md) |
| 7 Options and trade-offs | [04-decisions/ARCHITECTURE_OPTIONS_ANALYSIS.md](04-decisions/ARCHITECTURE_OPTIONS_ANALYSIS.md) |
| 8 Decisions | `04-decisions/ADR-001` … `ADR-006` |
| 9 Target architecture, security invariant, control placement | [03-architecture/TARGET_ARCHITECTURE.md](03-architecture/TARGET_ARCHITECTURE.md) |
| 10 Residual risks and what comes next | [03-architecture/RESIDUAL_RISK_REGISTER.md](03-architecture/RESIDUAL_RISK_REGISTER.md) |
| 11 Implementation design, controls, platform verification, cost and cleanup | [05-implementation/IMPLEMENTATION_DESIGN.md](05-implementation/IMPLEMENTATION_DESIGN.md) · [IMPLEMENTATION_CONTROLS.md](05-implementation/IMPLEMENTATION_CONTROLS.md) · [PLATFORM_VERIFICATION.md](05-implementation/PLATFORM_VERIFICATION.md) · [COST_AND_CLEANUP.md](05-implementation/COST_AND_CLEANUP.md) |
| 12 Build and run it | [05-implementation/README.md](05-implementation/README.md) |
| 13 Validation, including the three experiments that must be able to fail | [06-validation/VALIDATION_PLAN.md](06-validation/VALIDATION_PLAN.md) · [TEST_HARNESS_DESIGN.md](06-validation/TEST_HARNESS_DESIGN.md) · [RELEVANCE_CALIBRATION.md](06-validation/RELEVANCE_CALIBRATION.md) |
| 14 Traceability and evidence | [06-validation/TRACEABILITY_MATRIX.md](06-validation/TRACEABILITY_MATRIX.md) · `07-evidence/` |
| 15 Review and interview questions | [ARCHITECTURE_REVIEW_QUESTIONS.md](ARCHITECTURE_REVIEW_QUESTIONS.md) |

## Before you deploy

The implementation creates billable resources in **your own** sandbox AWS account. Read
[05-implementation/COST_AND_CLEANUP.md](05-implementation/COST_AND_CLEANUP.md), deploy, validate and clean up in one
session, and verify the cleanup.

**Evidence is portfolio evidence of the work performed, verified for this educational implementation under the tested
conditions — not a certification, a compliance statement or a claim that any system is secure.**

**Traceability check:** `python3 tools/traceability_check.py season-01-architecting-genai-aws/episode-02-sensitive-data-rag`,
from the repository root.
