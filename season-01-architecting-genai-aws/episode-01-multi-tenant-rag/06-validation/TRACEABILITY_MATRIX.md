<!-- template: tla-traceability-matrix/1 -->
# Traceability Matrix — Veltamere Document Assistant (engagement design seed)

```
business objective → requirement → decision area → control → test → observed result → portfolio evidence
```

**Seed state (engagement design):**
- Business objectives map to requirements through the `Source` column in [REQUIREMENTS.md](../02-requirements/REQUIREMENTS.md)
  and the objectives table in the [Architecture Brief](../01-business-context/ARCHITECTURE_BRIEF.md).
- The **Decision** column holds **decision questions (DQ-…)** until the architecture stage records decisions as ADRs. The
  checker validates ADR, control and test IDs; decision-question IDs are informational.
- **No controls exist yet**, so the Control column is empty. Every test is **NOT RUN**.
- `review:` marks requirements whose proof is a design or configuration review rather than a behavioural test.

| Requirement | Decision | Control | Test | Observed result | Evidence |
|---|---|---|---|---|---|
| BUS-001 | DQ-D, DQ-E | — | TST-DATA-016 | NOT RUN | — |
| BUS-002 | DQ-A | — | TST-OPS-017 | NOT RUN | — |
| FUN-001 | DQ-E | — | TST-ISO-001, TST-ISO-002 | NOT RUN | — |
| FUN-002 | DQ-D | — | TST-ISO-001, TST-ISO-002 | NOT RUN | — |
| FUN-003 | DQ-D, DQ-E | — | TST-DATA-014 | NOT RUN | — |
| SEC-001 | DQ-A, DQ-E | — | TST-ISO-003, TST-ISO-004, TST-SEN-011 | NOT RUN | — |
| SEC-002 | DQ-B, DQ-C | — | TST-SEC-007 | NOT RUN | — |
| SEC-003 | DQ-B | — | TST-SEC-005 | NOT RUN | — |
| SEC-004 | DQ-C, DQ-E | — | TST-ISO-003, TST-ISO-004, TST-SEN-011 | NOT RUN | — |
| SEC-005 | DQ-E | — | TST-SEC-006, TST-SEC-008 | NOT RUN | — |
| SEC-006 | DQ-D | — | TST-SEC-019, TST-ASM-010 | NOT RUN | — |
| SEC-007 | DQ-D | — | TST-SEC-020 | NOT RUN | — |
| SEC-008 | DQ-B, DQ-C, DQ-E | — | TST-SEC-013 | NOT RUN | — |
| SEC-009 | DQ-C | — | TST-SEC-009 | NOT RUN | — |
| SEC-010 | DQ-C | — | review: permissions of every component reviewed against the chosen design during architecture and verified in the implementation | NOT RUN | — |
| SEC-011 | DQ-A, DQ-F | — | review: protection at rest and in transit decided during architecture and verified by configuration review | NOT RUN | — |
| DATA-001 | DQ-D | — | TST-SEC-019 | NOT RUN | — |
| DATA-002 | DQ-D, DQ-E | — | TST-ISO-003, TST-ISO-004 | NOT RUN | — |
| DATA-003 | DQ-D | — | TST-ASM-010 | NOT RUN | — |
| NFR-001 | DQ-A, DQ-E | — | review: latency measured and reported during validation; not an isolation gate | NOT RUN | — |
| NFR-002 | DQ-A | — | TST-OPS-017 | NOT RUN | — |
| NFR-003 | DQ-A | — | review: design review during architecture; detailed failure behaviour is Episode 07 | NOT RUN | — |
| NFR-004 | DQ-A | — | review: cost model with a dated estimate during architecture | NOT RUN | — |
| OPS-001 | DQ-F | — | TST-OPS-015 | NOT RUN | — |
| OPS-002 | DQ-F | — | review: record contents reviewed during architecture and inspected in validation evidence | NOT RUN | — |
| OPS-003 | — | — | TST-OPS-018 | NOT RUN | — |
| OPS-004 | — | — | TST-OPS-012 | NOT RUN | — |
| OPS-005 | — | — | TST-OPS-018 | NOT RUN | — |
| CMP-001 | DQ-A, DQ-F | — | TST-ISO-003, TST-ISO-004, TST-OPS-015 | NOT RUN | — |
| CMP-002 | DQ-A | — | review: hosting region verified by configuration review of the deployment | NOT RUN | — |
