<!-- template: tla-requirements/1 -->
# Requirements — <engagement title>

Every requirement is **testable** ("X must never Y"), not an aspiration. IDs are stable once published.

**Families:** `BUS` business · `FUN` functional · `NFR` non-functional · `SEC` security · `DATA` data · `OPS` operational ·
`CMP` compliance · `CON` constraint. Priority: `MUST` · `SHOULD` · `COULD`.

Every `MUST` requirement must appear in `TRACEABILITY_MATRIX.md` with a test or a `review:` rationale.

| ID | Requirement | Rationale | Priority | Source | Verified by | Related decisions |
|---|---|---|---|---|---|---|
| SEC-000 | <testable statement> | <why it matters> | MUST | <stakeholder or constraint> | <TST-… or review> | <ADR-…> |
| DATA-000 | <testable statement> | <why> | SHOULD | <source> | <TST-…> | <ADR-…> |
