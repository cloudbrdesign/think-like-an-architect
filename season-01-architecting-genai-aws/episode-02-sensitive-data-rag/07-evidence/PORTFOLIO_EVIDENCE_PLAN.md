# Portfolio Evidence Plan — Kestrelmoor Knowledge Assistant

By the end of this engagement you will hold **portfolio evidence of the work you performed**: a record of how you took a
realistic sensitive-information retrieval problem from business need to a tested architecture.

> **Claim boundary.** This record does not certify competence. Think Like an Architect does not assess, verify or store
> it. Describe it as work you performed, not as a qualification. The strongest accurate claim about the system is
> *verified for the educational implementation under the tested conditions* — never "secure" or "compliant".

Use the [portfolio evidence template](../../../templates/PORTFOLIO_EVIDENCE.md) to assemble it at the end.

## What to keep, and where it comes from

| Evidence | What you keep | Where it comes from | Stage |
|---|---|---|---|
| The problem you addressed | Your summary of why authenticated employees must still not retrieve every section | Your notes on the [Architecture Brief](../01-business-context/ARCHITECTURE_BRIEF.md) | 1 |
| The requirements you worked against | The requirements you judged most important, with your reasons | Your notes on [Requirements](../02-requirements/REQUIREMENTS.md) | 2 |
| The options you considered | Your answers to the decision questions, including where eligibility could live and why you rejected the alternatives | [Decision questions](../04-decisions/ARCHITECTURE_DECISION_QUESTIONS.md), compared with the [options analysis](../04-decisions/ARCHITECTURE_OPTIONS_ANALYSIS.md) | 3 |
| The decisions you made | Your decision records, or your critique of the ADRs here | [ADRs](../04-decisions/) | 4 |
| The architecture you designed | Where grants and classification meet, where the constraint is built, what a tier does and does not do | [Target architecture](../03-architecture/TARGET_ARCHITECTURE.md) — redrawn or annotated by you | 5 |
| Your threat model | Attack paths, controls and the tests that exercise them | [Threat model](../03-architecture/THREAT_MODEL.md) and your additions | 5 |
| The implementation you built | Stack name, region, the commit you deployed from, the preflight result — **no account identifiers** | `python3 scripts/tla_ops.py preflight`, `deploy normal`; `git rev-parse HEAD` | 6 |
| The questions you asked as personas | One eligible and one ineligible request with their content-free audit records | `python3 -m harness ask <question> --as <persona>` | 7 |
| The validation you performed | `results.json` and `summary.md` from your full run | `python3 -m harness run --tests all` → `06-validation/results/<run-id>/` | 8 |
| Proof the tests can fail | The three experiment verdicts: what was broken, which tests failed, what verification did — and did not — catch | `python3 -m harness experiment 1`, `2`, `3` → `results/sen<n>-*` | 8 |
| Your traceability | The traceability matrix completed with your own results | [Traceability matrix](../06-validation/TRACEABILITY_MATRIX.md) and `tools/traceability_check.py` | 8 |
| Cleanup | The verified cleanup result showing nothing from the lab remains | `python3 scripts/tla_ops.py cleanup`, then `python3 -m harness verify-cleanup` | 9 |
| Residual risks and lessons | The largest remaining risk, what surprised you, what your evidence does **not** prove, and what production would add | Your reflection, using the [residual risks](../03-architecture/RESIDUAL_RISK_REGISTER.md) | 9 |
| Final architecture summary | One page you could present to a reviewer | [Architecture review questions](../ARCHITECTURE_REVIEW_QUESTIONS.md) | 10 |

## Assemble it (before you clean up)

1. **Export and bundle your runs.** Cleanup deletes the audit table, so do this first:
   `python3 -m harness export-audit --run-id <your full run>`, then
   `python3 -m harness evidence bundle --run-id <your full run> --run-id <each sen… run> --out <your folder>`.
2. **Clean up and keep the verification:** `python3 scripts/tla_ops.py cleanup`, then `python3 -m harness verify-cleanup`;
   bundle that result folder too.
3. **Write your reflection and one-page summary**, using the template.
4. **Review before sharing.** The harness replaces 12-digit account numbers, tokens and local paths. Also remove or blur
   API endpoint hostnames, user pool and client IDs, personal names and anything else identifying your account.

## What an example looks like

CloudBrewery's own runs are kept, redacted, in
[implementation-validation-2026-09-15](implementation-validation-2026-09-15/README.md). Use them to see the shape of the
evidence. **Do not present them as your own.**

## Describe it accurately

- **Scope:** for example, *"I deployed the Episode 02 learner implementation in my sandbox account in us-east-1, ran the
  validation suite (all tests passed), and showed with three failure experiments that the eligibility, metadata and
  revocation tests fail when their control is broken — including one failure that before-generation verification did
  not contain."*
- **Limits:** production scale, real corpora and entitlement systems, other regions, and platform limits that can change.
- **Wording to avoid:** "certified", "proven secure", "compliant", "guaranteed", or anything implying an independent
  assessment.
