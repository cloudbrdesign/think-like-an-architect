# Episode 01 — How to Build Multi-Tenant RAG Without Leaking Customer Data

> **You are the architect. Here is the client problem.**

**Status: engagement design (E1).** This folder currently contains the client problem, the requirements and the questions
the architecture must answer. **No architecture has been chosen and no implementation exists yet.** Nothing here deploys
anything, so this stage has no cloud cost.

The principle this episode is built around:

```
IDENTITY → AUTHORISATION → RETRIEVAL BOUNDARY
```

Tenant isolation must not depend on instructions given to a model. By the end of the engagement you must be able to show,
with tests that are allowed to fail, that one customer cannot retrieve another customer's information.

## Work through it in this order

| Step | Read / produce | File |
|---|---|---|
| 1 | Understand the client, the business problem and what failure costs | [Architecture Brief](01-business-context/ARCHITECTURE_BRIEF.md) |
| 2 | Study the requirements — especially the security invariants | [Requirements](02-requirements/REQUIREMENTS.md) |
| 3 | Separate what is assumed from what is constrained | [Assumptions and constraints](02-requirements/ASSUMPTIONS_AND_CONSTRAINTS.md) |
| 4 | See what can go wrong before choosing anything | [Initial risk register and threat-model inputs](03-architecture/INITIAL_RISK_REGISTER.md) |
| 5 | **Try to answer the decision questions yourself** | [Architecture decision questions](04-decisions/ARCHITECTURE_DECISION_QUESTIONS.md) |
| 6 | Know how the result will be judged | [Acceptance test intent](06-validation/ACCEPTANCE_TEST_INTENT.md) · [Traceability matrix](06-validation/TRACEABILITY_MATRIX.md) |
| 7 | Plan the record of your work | [Portfolio evidence plan](07-evidence/PORTFOLIO_EVIDENCE_PLAN.md) |
| 8 | Prepare to defend your design | [Architecture review questions](ARCHITECTURE_REVIEW_QUESTIONS.md) |

Architecture options, decisions, diagrams, the learner implementation, validation and cleanup are added in later stages.

## Check the traceability chain

```
python3 tools/traceability_check.py season-01-architecting-genai-aws/episode-01-multi-tenant-rag
```

## What this is not

Not a service tutorial. Not certification preparation. The evidence you produce is **portfolio evidence of the work you
performed** — it does not certify competence.
