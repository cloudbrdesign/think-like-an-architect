# Engagement templates

Templates for running an architecture engagement end to end. They contain **placeholders only**. Copy one into your
episode folder, replace the placeholders, and delete any optional section that would stay empty.

| Template | Use it to | Episode folder |
|---|---|---|
| [ARCHITECTURE_BRIEF.md](ARCHITECTURE_BRIEF.md) | Frame the business problem, stakeholders, constraints and assumptions | `01-business-context/` |
| [REQUIREMENTS.md](REQUIREMENTS.md) | State testable requirements with stable IDs | `02-requirements/` |
| [OPTIONS_ANALYSIS.md](OPTIONS_ANALYSIS.md) | Compare credible alternatives for a consequential decision | `04-decisions/` |
| [ADR.md](ADR.md) | Record a decision, its alternatives, consequences and the controls it introduces | `04-decisions/` |
| [THREAT_MODEL.md](THREAT_MODEL.md) | Find attack paths and map them to controls and tests | `03-architecture/` |
| [DIAGRAM_CONVENTIONS.md](DIAGRAM_CONVENTIONS.md) | Draw diagrams that answer one question each | `03-architecture/diagrams/` |
| [VALIDATION_PLAN.md](VALIDATION_PLAN.md) | Plan tests that prove requirements — including refusals | `06-validation/` |
| [TRACEABILITY_MATRIX.md](TRACEABILITY_MATRIX.md) | Connect requirement → decision → control → test → result → evidence | `06-validation/` |
| [COST_AND_CLEANUP.md](COST_AND_CLEANUP.md) | State billable resources and cleanup before you deploy | `05-implementation/`, `cleanup/` |
| [PORTFOLIO_EVIDENCE.md](PORTFOLIO_EVIDENCE.md) | Assemble portfolio evidence of the work you performed | `07-evidence/` |
| [ARCHITECTURE_REVIEW.md](ARCHITECTURE_REVIEW.md) | Defend the architecture against hard questions | episode root |

## The chain

```
business problem → requirement → decision → control → test → observed result → portfolio evidence
```

IDs are used only where they make that chain answerable: requirements (`SEC-001`, `DATA-001`, …), assumptions
(`ASM-001`), decisions (`ADR-001`), controls (`CTL-001`) and tests (`TST-ISO-001`). Check your chain with:

```
python3 tools/traceability_check.py <your-episode-folder>
python3 tools/traceability_check.py <your-episode-folder> --why ADR-001
python3 tools/traceability_check.py <your-episode-folder> --proof SEC-001
```
