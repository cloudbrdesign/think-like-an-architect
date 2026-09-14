<!-- template: tla-traceability-matrix/1 -->
# Traceability Matrix — Veltamere Document Assistant

```
business objective → requirement → decision (ADR) → control (CTL) → test → observed result → portfolio evidence
```

**State: architecture (E2), proposed.**
- Every row now names the **decisions** (ADRs in [04-decisions](../04-decisions/)) and the **controls** they introduce
  (CTL IDs, defined in each ADR's "Controls introduced" table).
- Business objectives map to requirements through the `Source` column in
  [REQUIREMENTS.md](../02-requirements/REQUIREMENTS.md) and the objectives table in the
  [Architecture Brief](../01-business-context/ARCHITECTURE_BRIEF.md).
- **No control is implemented and no test has run**, so every result is **NOT RUN**. Test designs are in
  [VALIDATION_PLAN.md](VALIDATION_PLAN.md).
- `review:` marks requirements whose proof is a design or configuration review rather than a behavioural test.

Ask the chain questions with the checker:

```
python3 tools/traceability_check.py season-01-architecting-genai-aws/episode-01-multi-tenant-rag --why ADR-001
python3 tools/traceability_check.py season-01-architecting-genai-aws/episode-01-multi-tenant-rag --proof SEC-001
```

| Requirement | Decision | Control | Test | Observed result | Evidence |
|---|---|---|---|---|---|
| BUS-001 | ADR-002, ADR-004 | CTL-005, CTL-011 | TST-DATA-016 | NOT RUN | — |
| BUS-002 | ADR-001, ADR-002 | CTL-005, CTL-006 | TST-OPS-017 | NOT RUN | — |
| FUN-001 | ADR-005, ADR-007 | CTL-015, CTL-018, CTL-022 | TST-ISO-001, TST-ISO-002 | NOT RUN | — |
| FUN-002 | ADR-004 | CTL-011 | TST-ISO-001, TST-ISO-002 | NOT RUN | — |
| FUN-003 | ADR-004, ADR-005 | CTL-014, CTL-017 | TST-DATA-014 | NOT RUN | — |
| SEC-001 | ADR-001, ADR-005 | CTL-001, CTL-015, CTL-017, CTL-018 | TST-ISO-003, TST-ISO-004, TST-SEN-011, TST-SEC-021 | NOT RUN | — |
| SEC-002 | ADR-002 | CTL-003 | TST-SEC-007 | NOT RUN | — |
| SEC-003 | ADR-002 | CTL-004, CTL-006 | TST-SEC-005 | NOT RUN | — |
| SEC-004 | ADR-003, ADR-005 | CTL-007, CTL-015 | TST-ISO-003, TST-ISO-004, TST-SEN-011 | NOT RUN | — |
| SEC-005 | ADR-005, ADR-007 | CTL-016, CTL-022 | TST-SEC-006, TST-SEC-008 | NOT RUN | — |
| SEC-006 | ADR-004 | CTL-011, CTL-012 | TST-SEC-019, TST-ASM-010 | NOT RUN | — |
| SEC-007 | ADR-004 | CTL-013 | TST-SEC-020, TST-SEC-023 | NOT RUN | — |
| SEC-008 | ADR-002, ADR-003, ADR-004, ADR-005 | CTL-005, CTL-007, CTL-012, CTL-015 | TST-SEC-013 | NOT RUN | — |
| SEC-009 | ADR-003 | CTL-008, CTL-009, CTL-014, CTL-021 | TST-SEC-009, TST-SEC-023 | NOT RUN | — |
| SEC-010 | ADR-003 | CTL-008, CTL-010, CTL-013 | TST-SEC-023 | NOT RUN | — |
| SEC-011 | ADR-001, ADR-006, ADR-007 | CTL-002, CTL-020, CTL-024 | review: encryption at rest and in transit, and content-free logging, verified by configuration review of every store, log group and model-logging setting | NOT RUN | — |
| DATA-001 | ADR-004 | CTL-011 | TST-SEC-019 | NOT RUN | — |
| DATA-002 | ADR-001, ADR-005 | CTL-001, CTL-015 | TST-ISO-003, TST-ISO-004 | NOT RUN | — |
| DATA-003 | ADR-004 | CTL-012, CTL-017, CTL-019 | TST-ASM-010, TST-SEC-022 | NOT RUN | — |
| NFR-001 | ADR-005, ADR-007 | — | review: latency measured and reported during validation (registry read, retrieval, ownership verification, generation); not an isolation gate | NOT RUN | — |
| NFR-002 | ADR-001 | CTL-005 | TST-OPS-017 | NOT RUN | — |
| NFR-003 | ADR-001, ADR-007 | — | review: assistant components are separate from the core platform and fail without affecting it; detailed failure behaviour is Episode 07 | NOT RUN | — |
| NFR-004 | ADR-001 | — | review: cost structure in 03-architecture/COST_AND_SCALE_ANALYSIS.md; dated estimate at build authorisation | NOT RUN | — |
| OPS-001 | ADR-006 | CTL-019 | TST-OPS-015 | NOT RUN | — |
| OPS-002 | ADR-006, ADR-007 | CTL-020, CTL-024 | TST-OPS-015 | NOT RUN | — |
| OPS-003 | — | — | TST-OPS-018 | NOT RUN | — |
| OPS-004 | — | — | TST-OPS-012 | NOT RUN | — |
| OPS-005 | — | — | TST-OPS-018 | NOT RUN | — |
| CMP-001 | ADR-001, ADR-006 | CTL-015, CTL-019 | TST-ISO-003, TST-ISO-004, TST-OPS-015 | NOT RUN | — |
| CMP-002 | ADR-001, ADR-007 | CTL-002, CTL-023 | review: region of every store, index and model endpoint verified by configuration review; no inference routing to other regions | NOT RUN | — |
