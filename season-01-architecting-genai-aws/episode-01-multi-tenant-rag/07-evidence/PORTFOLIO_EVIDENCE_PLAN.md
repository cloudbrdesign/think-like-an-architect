# Portfolio Evidence Plan — Veltamere Document Assistant

By the end of this engagement you will hold **portfolio evidence of the work you performed**: a record of how you took a
realistic multi-tenant retrieval problem from business need to a tested architecture.

> **Claim boundary.** This record does not certify competence. Think Like an Architect does not assess, verify or store
> it. Describe it as work you performed, not as a qualification.

Use the [portfolio evidence template](../../../templates/PORTFOLIO_EVIDENCE.md) to assemble it at the end.

## What to keep, and where it comes from

| Evidence | What you keep | Where it comes from | Stage |
|---|---|---|---|
| The problem you addressed | Your summary of the client problem and why isolation failure matters to this business | Your notes on the [Architecture Brief](../01-business-context/ARCHITECTURE_BRIEF.md) | 1 |
| The requirements you worked against | The requirements you judged most important, with your reasons | Your notes on [Requirements](../02-requirements/REQUIREMENTS.md) | 2 |
| The options you considered | Your own answers to the decision questions, including the options you rejected and why | Your answers to [Decision questions](../04-decisions/ARCHITECTURE_DECISION_QUESTIONS.md), compared with the [options analysis](../04-decisions/ARCHITECTURE_OPTIONS_ANALYSIS.md) | 3 |
| The decisions you made | Your decision records, each linked to the requirements that drove it — or your critique of the ADRs here | [ADRs](../04-decisions/) | 4 |
| The architecture you designed | Diagrams that show where identity is trusted, where authorisation is enforced and where the retrieval boundary is | [Diagrams](../03-architecture/diagrams/) — redrawn or annotated by you | 5 |
| Your threat model | Attack paths, controls and the tests that exercise them | [Threat model](../03-architecture/THREAT_MODEL.md) and your additions | 5 |
| The implementation you built | Stack name, region, commit you deployed from, the preflight result — **no account identifiers** | Output of `scripts/preflight.sh` and `scripts/deploy.sh`; `git rev-parse HEAD` | 6 |
| The attacks you tried | A forged-tenant request and its audit record, showing tenant context and constraint unchanged | `python3 -m harness ask --forge …` and `python3 -m harness inspect event <id>` | 7 |
| The validation you performed | `results.json` and `summary.md` from your full run, including the refused cross-tenant attempts | `python3 -m harness run --suite all` → `06-validation/results/<run-id>/` | 8 |
| Proof the tests can fail | The sensitivity verdict and the variant results: isolation tests FAIL with the primary control removed, PASS before and after | `scripts/sensitivity-run.sh` → `results/sen-<stamp>-*` | 8 |
| Your traceability | The traceability matrix completed with your own results | [Traceability matrix](../06-validation/TRACEABILITY_MATRIX.md) and `tools/traceability_check.py` | 8 |
| Cleanup | The `verify-cleanup` result showing nothing from the lab remains | `scripts/cleanup.sh` then `python3 -m harness verify-cleanup` | 9 |
| Residual risks and lessons | The largest remaining risk, what surprised you, what your evidence does **not** prove, and what production would add | Your reflection, using the [residual risks](../03-architecture/RESIDUAL_RISK_REGISTER.md) | 9 |
| Final architecture summary | One page you could present to a reviewer, answering the review questions with your artifacts | [Architecture review questions](../ARCHITECTURE_REVIEW_QUESTIONS.md) | 10 |

## Assemble it (before you clean up)

1. **Bundle your run results.** The audit table is deleted by cleanup, so do this first:
   `python3 -m harness evidence bundle --run-id <your full run> --run-id <each sen-… run> --out <your folder>`
2. **Clean up and keep the verification:**
   `scripts/cleanup.sh`, then `python3 -m harness verify-cleanup`. Copy its result folder too.
3. **Write your reflection and one-page summary**, using the template.
4. **Review before sharing.** The harness already replaces 12-digit account numbers with `<account>`. Also remove or blur:
   - API endpoint hostnames, and user pool and client IDs in screenshots;
   - personal names, email addresses and your local paths;
   - anything else identifying your account.

   Never include tokens or passwords — the harness never records them.

## What an example looks like

CloudBrewery's own run is kept, redacted, in [implementation-validation-2026-09-14](implementation-validation-2026-09-14/README.md). Use it to see
the shape of the evidence. **Do not present it as your own** — your portfolio is evidence of the work *you* performed.

## Describe it accurately

- **Scope:** say what you did and what the evidence showed, under which conditions. For example: *"I deployed the
  Episode 01 learner implementation in my sandbox account in us-east-1, ran the validation suite (all tests passed), and
  showed with the sensitivity test that the cross-tenant tests fail when the tenant constraint is removed."*
- **Limits:** say what it does not show — for example, production-scale isolation, performance under load, or behaviour
  in other regions.
- **Wording to avoid:** "certified", "proven competence", "guaranteed secure", or any wording that implies an independent
  assessment.
