# Validation results — fresh-normal-all

Variant **normal** · stack `tla-s01e01-normal` · region us-east-1 · commit `3af258e9b7a8bdde9b9aef9c33655c392aaca723` · 2026-09-14T07:52:57+00:00 → 2026-09-14T07:58:56+00:00

PASS 22 · FAIL 0 · ERROR 0 · NOT_RUN 0 · NOT_APPLICABLE 0

| Test | Verifies | Status | Key observation | Evidence |
|---|---|---|---|---|
| `TST-SEC-023` | SEC-009, SEC-010, SEC-007 | PASS | every capability held only by its intended principal; no application role holds the FC-04 deployment action | `evidence/TST-SEC-023.json` |
| `TST-SEC-005` | SEC-003 | PASS | body field refused; every other forged location ignored; membership unchanged | `evidence/TST-SEC-005.json` |
| `TST-SEC-013` | SEC-008 | PASS | cases 1–3 refused before retrieval in the deployment; cases 4–7 fail closed at component level | `evidence/TST-SEC-013.json` |
| `TST-ISO-001` | FUN-001, FUN-002 | PASS | 3 chunks retrieved, all tenant-a; cited 1 own document(s) | `evidence/TST-ISO-001.json` |
| `TST-ISO-002` | FUN-001, FUN-002 | PASS | 3 chunks retrieved, all tenant-b; cited 1 own document(s) | `evidence/TST-ISO-002.json` |
| `TST-ISO-003` | SEC-001, SEC-004, DATA-002, CMP-001 | PASS | 0 tenant-b documents retrieved across 6 targeted questions; preconditions met | `evidence/TST-ISO-003.json` |
| `TST-ISO-004` | SEC-001, SEC-004, DATA-002, CMP-001 | PASS | 0 tenant-a documents retrieved across 6 targeted questions; preconditions met | `evidence/TST-ISO-004.json` |
| `TST-SEC-006` | SEC-005 | PASS | constraint hash identical to baseline; no foreign retrieval | `evidence/TST-SEC-006.json` |
| `TST-SEC-008` | SEC-005 | PASS | single retrieval under tenant-a; hostile document retrieved=True; no foreign content | `evidence/TST-SEC-008.json` |
| `TST-SEC-021` | SEC-001, FUN-001 | PASS | 11 citations across 7 responses, all allow-listed and own | `evidence/TST-SEC-021.json` |
| `TST-SEC-022` | DATA-003, SEC-001 | PASS | divergent chunk retrieved under tenant-b; response withheld; OWNERSHIP_MISMATCH recorded | `evidence/TST-SEC-022.json` |
| `TST-SEC-009` | SEC-009 | PASS | direct invoke denied by explicit Deny; no other retrieval principal; originals unreadable directly; cross-tenant open not found; no debug or override path | `evidence/TST-SEC-009.json` |
| `TST-SEC-019` | SEC-006, DATA-001 | PASS | 4 field attempts refused, nothing stored; embedded claim ignored; owner tenant-a | `evidence/TST-SEC-019.json` |
| `TST-SEC-020` | SEC-007 | PASS | no user route changes ownership; 4 recorded correction steps; new tenant-b document via normal upload | `evidence/TST-SEC-020.json` |
| `TST-OPS-015` | OPS-001, OPS-002, CMP-001 | PASS | 27 records complete and content-free; 245 log events scanned, 0 content hits; model logging disabled | `evidence/TST-OPS-015.json` |
| `TST-OPS-017` | BUS-002, NFR-002 | PASS | tenant-c onboarded by registry entry + membership only; C↔A, C↔B, A→C isolated | `evidence/TST-OPS-017.json` |
| `TST-DATA-014` | FUN-003 | PASS | deleted document never cited; removed from index; cross-tenant delete not found (fixture restored) | `evidence/TST-DATA-014.json` |
| `TST-DATA-016` | BUS-001 | PASS | query and upload refused while disabled; tenant re-enabled | `evidence/TST-DATA-016.json` |
| `TST-ASM-010` | SEC-006, DATA-003 | PASS | (a) quarantine verified at component level; (b) exposed as residual risk RR-03, confined to tenant-a, removed | `evidence/TST-ASM-010.json` |
| `TST-SEC-007` | SEC-002 | PASS | all six token cases rejected at the edge; no service ran | `evidence/TST-SEC-007.json` |
| `RT-15` | SEC-004 | PASS | variant guards refused every wrong-target attempt | `evidence/RT-15.json` |
| `RT-16` | OPS-004 | PASS | cleanup refused the wrong account; normal stack still CREATE_COMPLETE | `evidence/RT-16.json` |
