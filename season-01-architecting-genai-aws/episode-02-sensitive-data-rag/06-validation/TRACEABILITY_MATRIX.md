<!-- template: tla-traceability-matrix/1 -->
# Traceability Matrix (draft) — Kestrelmoor Knowledge Assistant

```
business objective → requirement → decision (ADR) → control (CTL) → test → observed result → portfolio evidence
```

**State:** implementation built and validated on 2026-09-15 — primary run and a fresh-copy repeat from a clean clone.
- **Results come only from executed tests.** The fresh-copy run's own suite and experiment results are in its folders under `07-evidence/` and matched the primary run with no differences.
- Rows whose proof is a `review:` rationale stay `NOT RUN`: no executed test proves them.

| Requirement | Decision | Control | Test | Observed result | Evidence |
|---|---|---|---|---|---|
| BUS-001 | ADR-001 | CTL-001 | TST-ELG-001 | PASS | 07-evidence/implementation-validation-2026-09-15/primary-20260915-normal-all/evidence/TST-ELG-001.json |
| BUS-002 | ADR-001, ADR-002 | CTL-001, CTL-003 | TST-CHG-001 | PASS | 07-evidence/implementation-validation-2026-09-15/primary-20260915-normal-all/evidence/TST-CHG-001.json |
| BUS-003 | ADR-001, ADR-003 | CTL-001, CTL-006 | review: new domains and case types are entitlement-registry and records-system configuration; no assistant code path names a specific domain or case | NOT RUN | — |
| FUN-001 | ADR-004, ADR-005 | CTL-011, CTL-015 | TST-ELG-001 | PASS | 07-evidence/implementation-validation-2026-09-15/primary-20260915-normal-all/evidence/TST-ELG-001.json |
| FUN-002 | ADR-001, ADR-004 | CTL-001, CTL-011, CTL-012 | TST-ELG-002, TST-ELG-007 | PASS | 07-evidence/implementation-validation-2026-09-15/primary-20260915-normal-all/evidence/TST-ELG-002.json, 07-evidence/implementation-validation-2026-09-15/primary-20260915-normal-all/evidence/TST-ELG-007.json |
| FUN-003 | ADR-005 | CTL-016 | TST-ELG-008 | PASS | 07-evidence/implementation-validation-2026-09-15/primary-20260915-normal-all/evidence/TST-ELG-008.json |
| FUN-004 | ADR-003 | CTL-008 | TST-ELG-004 | PASS | 07-evidence/implementation-validation-2026-09-15/primary-20260915-normal-all/evidence/TST-ELG-004.json |
| SEC-001 | ADR-001, ADR-004, ADR-005 | CTL-001, CTL-011, CTL-012, CTL-014, CTL-015 | TST-ELG-003, TST-ELG-005, TST-ELG-006, TST-ELG-009, TST-SEN-001 | PASS | 07-evidence/implementation-validation-2026-09-15/primary-20260915-normal-all/evidence/TST-ELG-003.json, 07-evidence/implementation-validation-2026-09-15/primary-20260915-normal-all/evidence/TST-ELG-005.json, 07-evidence/implementation-validation-2026-09-15/primary-20260915-normal-all/evidence/TST-ELG-006.json, 07-evidence/implementation-validation-2026-09-15/primary-20260915-normal-all/evidence/TST-ELG-009.json, 07-evidence/implementation-validation-2026-09-15/sen1-primary-20260915-r2-verdict/evidence/TST-SEN-001.json |
| SEC-002 | ADR-002 | CTL-002 | TST-SEC-001 | PASS | 07-evidence/implementation-validation-2026-09-15/primary-20260915-normal-all/evidence/TST-SEC-001.json |
| SEC-003 | ADR-002 | CTL-003 | TST-SEC-002, TST-CHG-001 | PASS | 07-evidence/implementation-validation-2026-09-15/primary-20260915-normal-all/evidence/TST-SEC-002.json, 07-evidence/implementation-validation-2026-09-15/primary-20260915-normal-all/evidence/TST-CHG-001.json |
| SEC-004 | ADR-004 | CTL-011, CTL-012, CTL-013 | TST-ELG-003, TST-SEN-001 | PASS | 07-evidence/implementation-validation-2026-09-15/primary-20260915-normal-all/evidence/TST-ELG-003.json, 07-evidence/implementation-validation-2026-09-15/sen1-primary-20260915-r2-verdict/evidence/TST-SEN-001.json |
| SEC-005 | ADR-004 | CTL-013 | TST-SEC-003 | PASS | 07-evidence/implementation-validation-2026-09-15/primary-20260915-normal-all/evidence/TST-SEC-003.json |
| SEC-006 | ADR-001, ADR-004 | CTL-001, CTL-011, CTL-012 | TST-ELG-006, TST-ELG-007, TST-ELG-009 | PASS | 07-evidence/implementation-validation-2026-09-15/primary-20260915-normal-all/evidence/TST-ELG-006.json, 07-evidence/implementation-validation-2026-09-15/primary-20260915-normal-all/evidence/TST-ELG-007.json, 07-evidence/implementation-validation-2026-09-15/primary-20260915-normal-all/evidence/TST-ELG-009.json |
| SEC-007 | ADR-002, ADR-003 | CTL-004, CTL-007 | TST-SEC-005, TST-SEC-006, TST-DATA-001, TST-DATA-002 | PASS | 07-evidence/implementation-validation-2026-09-15/primary-20260915-normal-all/evidence/TST-SEC-005.json, 07-evidence/implementation-validation-2026-09-15/primary-20260915-normal-all/evidence/TST-SEC-006.json, 07-evidence/implementation-validation-2026-09-15/primary-20260915-normal-all/evidence/TST-DATA-001.json, 07-evidence/implementation-validation-2026-09-15/primary-20260915-normal-all/evidence/TST-DATA-002.json |
| SEC-008 | ADR-005 | CTL-014 | TST-SEC-007, TST-SEN-002 | PASS | 07-evidence/implementation-validation-2026-09-15/primary-20260915-normal-all/evidence/TST-SEC-007.json, 07-evidence/implementation-validation-2026-09-15/sen2-primary-20260915-verdict/evidence/TST-SEN-002.json |
| SEC-009 | ADR-004 | CTL-005 | TST-SEC-004 | PASS | 07-evidence/implementation-validation-2026-09-15/primary-20260915-normal-all/evidence/TST-SEC-004.json |
| SEC-010 | ADR-002 | CTL-003 | TST-CHG-001, TST-SEN-003 | PASS | 07-evidence/implementation-validation-2026-09-15/primary-20260915-normal-all/evidence/TST-CHG-001.json, 07-evidence/implementation-validation-2026-09-15/sen3-primary-20260915-verdict/evidence/TST-SEN-003.json |
| SEC-011 | ADR-005 | CTL-014 | TST-CHG-002 | PASS | 07-evidence/implementation-validation-2026-09-15/primary-20260915-normal-all/evidence/TST-CHG-002.json |
| SEC-012 | ADR-006 | CTL-018, CTL-019 | TST-OBS-001 | PASS | 07-evidence/implementation-validation-2026-09-15/primary-20260915-normal-all/evidence/TST-OBS-001.json |
| SEC-013 | ADR-004, ADR-003 | CTL-005, CTL-010 | TST-SEC-004 | PASS | 07-evidence/implementation-validation-2026-09-15/primary-20260915-normal-all/evidence/TST-SEC-004.json |
| DATA-001 | ADR-003 | CTL-007 | TST-DATA-002 | PASS | 07-evidence/implementation-validation-2026-09-15/primary-20260915-normal-all/evidence/TST-DATA-002.json |
| DATA-002 | ADR-003 | CTL-006 | TST-DATA-003 | PASS | 07-evidence/implementation-validation-2026-09-15/primary-20260915-normal-all/evidence/TST-DATA-003.json |
| DATA-003 | ADR-003 | CTL-008 | TST-ELG-004, TST-DATA-005, TST-SEN-002 | PASS | 07-evidence/implementation-validation-2026-09-15/primary-20260915-normal-all/evidence/TST-ELG-004.json, 07-evidence/implementation-validation-2026-09-15/primary-20260915-normal-all/evidence/TST-DATA-005.json, 07-evidence/implementation-validation-2026-09-15/sen2-primary-20260915-verdict/evidence/TST-SEN-002.json |
| DATA-004 | ADR-003 | CTL-009 | TST-DATA-004 | PASS | 07-evidence/implementation-validation-2026-09-15/primary-20260915-normal-all/evidence/TST-DATA-004.json |
| DATA-005 | ADR-003 | CTL-007 | TST-DATA-001, TST-DATA-002 | PASS | 07-evidence/implementation-validation-2026-09-15/primary-20260915-normal-all/evidence/TST-DATA-001.json, 07-evidence/implementation-validation-2026-09-15/primary-20260915-normal-all/evidence/TST-DATA-002.json |
| DATA-006 | ADR-003, ADR-005, ADR-006 | CTL-010, CTL-017, CTL-019 | TST-DATA-006, TST-OBS-001 | PASS | 07-evidence/implementation-validation-2026-09-15/primary-20260915-normal-all/evidence/TST-DATA-006.json, 07-evidence/implementation-validation-2026-09-15/primary-20260915-normal-all/evidence/TST-OBS-001.json |
| DATA-007 | ADR-003 | CTL-008 | TST-DATA-005 | PASS | 07-evidence/implementation-validation-2026-09-15/primary-20260915-normal-all/evidence/TST-DATA-005.json |
| NFR-001 | ADR-002 | CTL-003 | TST-SCALE-001 | PASS | 07-evidence/implementation-validation-2026-09-15/primary-20260915-normal-all/evidence/TST-SCALE-001.json |
| NFR-002 | ADR-002, ADR-004 | CTL-003, CTL-013 | TST-SCALE-001 | PASS | 07-evidence/implementation-validation-2026-09-15/primary-20260915-normal-all/evidence/TST-SCALE-001.json |
| NFR-003 | ADR-002 | CTL-004 | TST-SEC-005 | PASS | 07-evidence/implementation-validation-2026-09-15/primary-20260915-normal-all/evidence/TST-SEC-005.json |
| NFR-004 | ADR-004 | — | review: cost per 1,000 questions estimated for the two-tier design before build | NOT RUN | — |
| NFR-005 | — | — | review: pilot business-hours availability; no specific control | NOT RUN | — |
| OPS-001 | ADR-006 | CTL-020 | TST-OBS-002 | PASS | 07-evidence/implementation-validation-2026-09-15/primary-20260915-normal-all/evidence/TST-OBS-002.json |
| OPS-002 | ADR-006 | CTL-018, CTL-020 | TST-OBS-002 | PASS | 07-evidence/implementation-validation-2026-09-15/primary-20260915-normal-all/evidence/TST-OBS-002.json |
| OPS-003 | — | — | TST-OPS-001 | PASS | 07-evidence/implementation-validation-2026-09-15/fresh-20260915-r3-TST-OPS-001/evidence/TST-OPS-001.json |
| CMP-001 | ADR-003 | CTL-009 | TST-DATA-004 | PASS | 07-evidence/implementation-validation-2026-09-15/primary-20260915-normal-all/evidence/TST-DATA-004.json |
| CMP-002 | ADR-006 | CTL-018 | review: audit retention configured to Kestrelmoor's records policy | NOT RUN | — |
