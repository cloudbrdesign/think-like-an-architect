<!-- template: tla-traceability-matrix/1 -->
# Traceability Matrix — Veltamere Document Assistant

```
business objective → requirement → decision (ADR) → control (CTL) → test → observed result → portfolio evidence
```

**State: educational implementation (E4), observed on 2026-09-14.**
- Every row now names the **decisions** (ADRs in [04-decisions](../04-decisions/)) and the **controls** they introduce
  (CTL IDs, defined in each ADR's "Controls introduced" table).
- Business objectives map to requirements through the `Source` column in
  [REQUIREMENTS.md](../02-requirements/REQUIREMENTS.md) and the objectives table in the
  [Architecture Brief](../01-business-context/ARCHITECTURE_BRIEF.md).
- Results come from the fresh-copy validation run in [07-evidence/e4-validation-2026-09-14](../07-evidence/e4-validation-2026-09-14/README.md).
  The Evidence column lists the implementing source first, then the result file. Test designs are in
  [VALIDATION_PLAN.md](VALIDATION_PLAN.md).
- `NOT VERIFIED` marks reviews this run did not complete: latency summary (NFR-001), failure isolation from the
  core platform (NFR-003, Episode 07) and the billed session cost (NFR-004, read once billing data is available).
- `review:` marks requirements whose proof is a design or configuration review rather than a behavioural test.

Ask the chain questions with the checker:

```
python3 tools/traceability_check.py season-01-architecting-genai-aws/episode-01-multi-tenant-rag --why ADR-001
python3 tools/traceability_check.py season-01-architecting-genai-aws/episode-01-multi-tenant-rag --proof SEC-001
```

| Requirement | Decision | Control | Test | Observed result | Evidence |
|---|---|---|---|---|---|
| BUS-001 | ADR-002, ADR-004 | CTL-005, CTL-011 | TST-DATA-016 | PASS | 05-implementation/app/shared/tenant_context.py, 07-evidence/e4-validation-2026-09-14/fresh-normal-all/evidence/TST-DATA-016.json |
| BUS-002 | ADR-001, ADR-002 | CTL-005, CTL-006 | TST-OPS-017 | PASS | 05-implementation/app/shared/tenant_context.py, 06-validation/harness/fixtures.py, 07-evidence/e4-validation-2026-09-14/fresh-normal-all/evidence/TST-OPS-017.json |
| FUN-001 | ADR-005, ADR-007 | CTL-015, CTL-018, CTL-022 | TST-ISO-001, TST-ISO-002 | PASS | 05-implementation/app/shared/retrieval_scope.py, 05-implementation/app/shared/citations.py, 05-implementation/app/query/prompt.py, 07-evidence/e4-validation-2026-09-14/fresh-normal-all/evidence/TST-ISO-001.json, 07-evidence/e4-validation-2026-09-14/fresh-normal-all/evidence/TST-ISO-002.json |
| FUN-002 | ADR-004 | CTL-011 | TST-ISO-001, TST-ISO-002 | PASS | 05-implementation/app/shared/ownership.py, 07-evidence/e4-validation-2026-09-14/fresh-normal-all/evidence/TST-ISO-001.json, 07-evidence/e4-validation-2026-09-14/fresh-normal-all/evidence/TST-ISO-002.json |
| FUN-003 | ADR-004, ADR-005 | CTL-014, CTL-017 | TST-DATA-014 | PASS | 05-implementation/app/ingestion/handler.py, 05-implementation/app/shared/ownership_verification.py, 07-evidence/e4-validation-2026-09-14/fresh-normal-all/evidence/TST-DATA-014.json |
| SEC-001 | ADR-001, ADR-005 | CTL-001, CTL-015, CTL-017, CTL-018 | TST-ISO-003, TST-ISO-004, TST-SEN-011, TST-SEC-021 | PASS | 05-implementation/app/shared/retrieval_scope.py, 05-implementation/app/shared/ownership_verification.py, 05-implementation/app/shared/citations.py, 07-evidence/e4-validation-2026-09-14/fresh-normal-all/evidence/TST-ISO-003.json, 07-evidence/e4-validation-2026-09-14/fresh-normal-all/evidence/TST-ISO-004.json, 07-evidence/e4-validation-2026-09-14/sen-20260914T075857Z-verdict/evidence/TST-SEN-011.json, 07-evidence/e4-validation-2026-09-14/fresh-normal-all/evidence/TST-SEC-021.json |
| SEC-002 | ADR-002 | CTL-003 | TST-SEC-007 | PASS | 05-implementation/infrastructure/template.yaml, 07-evidence/e4-validation-2026-09-14/fresh-normal-all/evidence/TST-SEC-007.json |
| SEC-003 | ADR-002 | CTL-004, CTL-006 | TST-SEC-005 | PASS | 05-implementation/app/shared/tenant_context.py, 05-implementation/app/shared/tenant_claims.py, 07-evidence/e4-validation-2026-09-14/fresh-normal-all/evidence/TST-SEC-005.json |
| SEC-004 | ADR-003, ADR-005 | CTL-007, CTL-015 | TST-ISO-003, TST-ISO-004, TST-SEN-011 | PASS | 05-implementation/app/shared/retrieval_scope.py, 05-implementation/app/shared/retrieval_client.py, 07-evidence/e4-validation-2026-09-14/fresh-normal-all/evidence/TST-ISO-003.json, 07-evidence/e4-validation-2026-09-14/fresh-normal-all/evidence/TST-ISO-004.json, 07-evidence/e4-validation-2026-09-14/sen-20260914T075857Z-verdict/evidence/TST-SEN-011.json |
| SEC-005 | ADR-005, ADR-007 | CTL-016, CTL-022 | TST-SEC-006, TST-SEC-008 | PASS | 05-implementation/app/shared/retrieval_client.py, 05-implementation/app/query/prompt.py, 07-evidence/e4-validation-2026-09-14/fresh-normal-all/evidence/TST-SEC-006.json, 07-evidence/e4-validation-2026-09-14/fresh-normal-all/evidence/TST-SEC-008.json |
| SEC-006 | ADR-004 | CTL-011, CTL-012 | TST-SEC-019, TST-ASM-010 | PASS | 05-implementation/app/shared/ownership.py, 05-implementation/app/shared/request_schema.py, 07-evidence/e4-validation-2026-09-14/fresh-normal-all/evidence/TST-SEC-019.json, 07-evidence/e4-validation-2026-09-14/fresh-normal-all/evidence/TST-ASM-010.json |
| SEC-007 | ADR-004 | CTL-013 | TST-SEC-020, TST-SEC-023 | PASS | 05-implementation/app/shared/ownership.py, 05-implementation/scripts/operator/correct_attribution.py, 07-evidence/e4-validation-2026-09-14/fresh-normal-all/evidence/TST-SEC-020.json, 07-evidence/e4-validation-2026-09-14/fresh-normal-all/evidence/TST-SEC-023.json |
| SEC-008 | ADR-002, ADR-003, ADR-004, ADR-005 | CTL-005, CTL-007, CTL-012, CTL-015 | TST-SEC-013 | PASS | 05-implementation/app/shared/tenant_context.py, 05-implementation/app/shared/retrieval_scope.py, 07-evidence/e4-validation-2026-09-14/fresh-normal-all/evidence/TST-SEC-013.json |
| SEC-009 | ADR-003 | CTL-008, CTL-009, CTL-014, CTL-021 | TST-SEC-009, TST-SEC-023 | PASS | 05-implementation/infrastructure/template.yaml, 07-evidence/e4-validation-2026-09-14/fresh-normal-all/evidence/TST-SEC-009.json, 07-evidence/e4-validation-2026-09-14/fresh-normal-all/evidence/TST-SEC-023.json |
| SEC-010 | ADR-003 | CTL-008, CTL-010, CTL-013 | TST-SEC-023 | PASS | 05-implementation/infrastructure/template.yaml, 07-evidence/e4-validation-2026-09-14/fresh-normal-all/evidence/TST-SEC-023.json |
| SEC-011 | ADR-001, ADR-006, ADR-007 | CTL-002, CTL-020, CTL-024 | review: encryption at rest and in transit, and content-free logging, verified by configuration review of every store, log group and model-logging setting | PASS | 05-implementation/infrastructure/template.yaml, 05-implementation/app/shared/audit.py, 07-evidence/e4-validation-2026-09-14/fresh-normal-all/evidence/TST-OPS-015.json, 07-evidence/e4-validation-2026-09-14/fresh-normal-all/evidence/TST-SEC-023.json |
| DATA-001 | ADR-004 | CTL-011 | TST-SEC-019 | PASS | 05-implementation/app/shared/ownership.py, 07-evidence/e4-validation-2026-09-14/fresh-normal-all/evidence/TST-SEC-019.json |
| DATA-002 | ADR-001, ADR-005 | CTL-001, CTL-015 | TST-ISO-003, TST-ISO-004 | PASS | 05-implementation/app/shared/retrieval_scope.py, 07-evidence/e4-validation-2026-09-14/fresh-normal-all/evidence/TST-ISO-003.json, 07-evidence/e4-validation-2026-09-14/fresh-normal-all/evidence/TST-ISO-004.json |
| DATA-003 | ADR-004 | CTL-012, CTL-017, CTL-019 | TST-ASM-010, TST-SEC-022 | PASS | 05-implementation/app/shared/ownership.py, 05-implementation/app/shared/ownership_verification.py, 07-evidence/e4-validation-2026-09-14/fresh-normal-all/evidence/TST-ASM-010.json, 07-evidence/e4-validation-2026-09-14/fresh-normal-all/evidence/TST-SEC-022.json |
| NFR-001 | ADR-005, ADR-007 | — | review: latency measured and reported during validation (registry read, retrieval, ownership verification, generation); not an isolation gate | NOT VERIFIED | — |
| NFR-002 | ADR-001 | CTL-005 | TST-OPS-017 | PASS | 05-implementation/app/shared/tenant_context.py, 07-evidence/e4-validation-2026-09-14/fresh-normal-all/evidence/TST-OPS-017.json |
| NFR-003 | ADR-001, ADR-007 | — | review: assistant components are separate from the core platform and fail without affecting it; detailed failure behaviour is Episode 07 | NOT VERIFIED | — |
| NFR-004 | ADR-001 | — | review: cost structure in 03-architecture/COST_AND_SCALE_ANALYSIS.md; dated estimate at build authorisation | NOT VERIFIED | — |
| OPS-001 | ADR-006 | CTL-019 | TST-OPS-015 | PASS | 05-implementation/app/shared/audit.py, 07-evidence/e4-validation-2026-09-14/fresh-normal-all/evidence/TST-OPS-015.json |
| OPS-002 | ADR-006, ADR-007 | CTL-020, CTL-024 | TST-OPS-015 | PASS | 05-implementation/app/shared/audit.py, 05-implementation/scripts/tla_ops.py, 07-evidence/e4-validation-2026-09-14/fresh-normal-all/evidence/TST-OPS-015.json |
| OPS-003 | — | — | TST-OPS-018 | PASS | 05-implementation/README.md, 07-evidence/e4-validation-2026-09-14/FRESH_COPY_RUN.md |
| OPS-004 | — | — | TST-OPS-012 | PASS | 05-implementation/scripts/tla_ops.py, 06-validation/harness/cleanup_check.py, 07-evidence/e4-validation-2026-09-14/fresh-cleanup-all/evidence/TST-OPS-012.json |
| OPS-005 | — | — | TST-OPS-018 | PASS | 06-validation/harness/__main__.py, 07-evidence/e4-validation-2026-09-14/FRESH_COPY_RUN.md |
| CMP-001 | ADR-001, ADR-006 | CTL-015, CTL-019 | TST-ISO-003, TST-ISO-004, TST-OPS-015 | PASS | 05-implementation/app/shared/retrieval_scope.py, 05-implementation/app/shared/audit.py, 07-evidence/e4-validation-2026-09-14/fresh-normal-all/evidence/TST-ISO-003.json, 07-evidence/e4-validation-2026-09-14/fresh-normal-all/evidence/TST-ISO-004.json, 07-evidence/e4-validation-2026-09-14/fresh-normal-all/evidence/TST-OPS-015.json |
| CMP-002 | ADR-001, ADR-007 | CTL-002, CTL-023 | review: region of every store, index and model endpoint verified by configuration review; no inference routing to other regions | PASS | 05-implementation/infrastructure/template.yaml, 05-implementation/app/query/model_client.py, 07-evidence/e4-validation-2026-09-14/fresh-normal-all/evidence/TST-SEC-023.json |
