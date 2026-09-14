# Implementation validation evidence — fresh-copy run, 2026-09-14

Commit `3af258e9b7a8bdde9b9aef9c33655c392aaca723` · region us-east-1 · account numbers redacted · synthetic data only.
Portfolio evidence of the work performed — not certification.

| Folder | What it is |
|---|---|
| `fresh-normal-all/` | Full suite against the normal deployment (`results.json`, `summary.md`, `evidence/`) |
| `sen-20260914T075857Z-baseline/` · `-variant/` · `-cleanup/` · `-bracket/` · `-verdict/` | Sensitivity test: normal → variant with the primary control removed → variant destroyed → normal → verdict |
| `fresh-cleanup-all/` | Final authoritative cleanup verification |
| `FRESH_COPY_RUN.md` | Step-by-step timing and exit codes of the fresh-copy run |
| `LATENCY_SUMMARY.md` | NFR-001: coarse end-to-end latency from this run's evidence, and what it does not show |

## Results — normal deployment

| Test | Status | Key observation |
|---|---|---|
| `TST-SEC-023` | PASS | every capability held only by its intended principal; no application role holds the FC-04 deployment action |
| `TST-SEC-005` | PASS | body field refused; every other forged location ignored; membership unchanged |
| `TST-SEC-013` | PASS | cases 1–3 refused before retrieval in the deployment; cases 4–7 fail closed at component level |
| `TST-ISO-001` | PASS | 3 chunks retrieved, all tenant-a; cited 1 own document(s) |
| `TST-ISO-002` | PASS | 3 chunks retrieved, all tenant-b; cited 1 own document(s) |
| `TST-ISO-003` | PASS | 0 tenant-b documents retrieved across 6 targeted questions; preconditions met |
| `TST-ISO-004` | PASS | 0 tenant-a documents retrieved across 6 targeted questions; preconditions met |
| `TST-SEC-006` | PASS | constraint hash identical to baseline; no foreign retrieval |
| `TST-SEC-008` | PASS | single retrieval under tenant-a; hostile document retrieved=True; no foreign content |
| `TST-SEC-021` | PASS | 11 citations across 7 responses, all allow-listed and own |
| `TST-SEC-022` | PASS | divergent chunk retrieved under tenant-b; response withheld; OWNERSHIP_MISMATCH recorded |
| `TST-SEC-009` | PASS | direct invoke denied by explicit Deny; no other retrieval principal; originals unreadable directly; cross-tenant open not found; no debug or override path |
| `TST-SEC-019` | PASS | 4 field attempts refused, nothing stored; embedded claim ignored; owner tenant-a |
| `TST-SEC-020` | PASS | no user route changes ownership; 4 recorded correction steps; new tenant-b document via normal upload |
| `TST-OPS-015` | PASS | 27 records complete and content-free; 245 log events scanned, 0 content hits; model logging disabled |
| `TST-OPS-017` | PASS | tenant-c onboarded by registry entry + membership only; C↔A, C↔B, A→C isolated |
| `TST-DATA-014` | PASS | deleted document never cited; removed from index; cross-tenant delete not found (fixture restored) |
| `TST-DATA-016` | PASS | query and upload refused while disabled; tenant re-enabled |
| `TST-ASM-010` | PASS | (a) quarantine verified at component level; (b) exposed as residual risk RR-03, confined to tenant-a, removed |
| `TST-SEC-007` | PASS | all six token cases rejected at the edge; no service ran |
| `RT-15` | PASS | variant guards refused every wrong-target attempt |
| `RT-16` | PASS | cleanup refused the wrong account; normal stack still CREATE_COMPLETE |

## Sensitivity test

`TST-SEN-011` **PASS** — normal PASS → variant FAIL (foreign chunks retrieved, ownership verification fired) → variant destroyed → normal PASS

## Cleanup

`TST-OPS-012` **PASS** — CLEAN — normal, sensitivity (4 stale tag-index entries confirmed deleted)

## Red-team of the finished build

| # | Attack | Evidence | Result |
|---|---|---|---|
| 1 | Forged request tenant (body, query, header, path, question, self-service) | `TST-SEC-005` | PASS |
| 2 | Multiple tenant groups | `TST-SEC-013` | PASS |
| 3 | Malformed tenant group claim | `TST-SEC-013` (strict parser component tests (malformed, empty, unexpected syntax); Cognito cannot issue a malformed claim) | PASS |
| 4 | Missing membership | `TST-SEC-013` | PASS |
| 5 | Disabled tenant | `TST-DATA-016` | PASS |
| 6 | Direct Lambda invocation with forged claims | `TST-SEC-009` | PASS |
| 7 | Direct retrieval from an unauthorised role | `TST-SEC-023` (also TST-SEC-009 case 2) | PASS |
| 8 | Prompt requesting another tenant's documents | `TST-SEC-006` | PASS |
| 9 | Indirect prompt injection in an own document | `TST-SEC-008` | PASS |
| 10 | Forged ownership on upload, update or re-upload | `TST-SEC-019` (also TST-SEC-020) | PASS |
| 11 | Indexed chunk whose owner disagrees with the ownership record | `TST-SEC-022` (also component tests for missing owner attributes) | PASS |
| 12 | Cross-tenant deletion by identifier | `TST-DATA-014` | PASS |
| 13 | Citation and metadata leakage, fabricated citation | `TST-SEC-021` | PASS |
| 14 | Sensitive content in audit records or logs | `TST-OPS-015` | PASS |
| 15 | Sensitivity-stack targeting mistake | `RT-15` | PASS |
| 16 | Cleanup against the wrong stack, account or region | `RT-16` (account guard refused; a wrong region matches no episode resources) | PASS |

## Usage recorded in this evidence (for the cost check, VE-11)

| Measure | Count |
|---|---|
| api requests with audit records | 86 |
| operator retrievals for preconditions | 51 |
| responses with status 200 recorded | 57 |
