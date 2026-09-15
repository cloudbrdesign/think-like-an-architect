# Implementation Controls (control catalogue) — Kestrelmoor Knowledge Assistant

**Stage:** implementation, as built · **Date:** 2026-09-15 · **Status:** design accepted; controls implemented

**What this catalogue holds:** each approved control (defined in the ADRs' "Controls introduced" tables) as an
implementation specification. Module paths refer to [IMPLEMENTATION_DESIGN.md §10](IMPLEMENTATION_DESIGN.md#10-source-structure-planned-created-during-the-build).

**Evidence status:** produced by the validation runs under `07-evidence/`; results in the traceability matrix. Evidence
from verification spikes is recorded separately in [PLATFORM_VERIFICATION.md](PLATFORM_VERIFICATION.md) and is **not** validation evidence.

**Evidence file convention:** `07-evidence/<run>/evidence/<TST-ID>.json`, plus the shared run artifacts `audit.jsonl`,
`inventory.json`, `canary-scan.json` and `quarantine-report.json`.

| Control | ID | Requirement(s) | Component (module) | Authoritative input | Enforcement location | Failure mode | Observability | Validation test(s) | Evidence produced |
|---|---|---|---|---|---|---|---|---|---|
| Eligibility rule | CTL-001 | SEC-001, SEC-006, BUS-001, BUS-002, FUN-002 | `app/core/eligibility.py`, called by `app/query/policy_decision.py` | HR status and grant records (grants store); classification label and scope | Query function, before any retrieval | No decision → no retrieval | `decision.*` in audit | TST-ELG-001–009 | Per-test evidence with decision and retrieved list |
| Verified identity | CTL-002 | SEC-002 | HTTP API JWT authorizer; `handler.py` reads `sub` only | Identity provider signature, issuer, audience, expiry | Edge | 401; function not invoked | API access log; no audit item | TST-SEC-001 | `TST-SEC-001.json` (status codes; absence of audit items) |
| Per-request entitlements | CTL-003 | SEC-003, SEC-010, NFR-001, NFR-002, BUS-002 | `app/query/policy_decision.py` | Grants store (consistent reads), versions | Query function | Any error → CTL-004 | `hr_version`, `grants_version` in audit | TST-SEC-002, TST-CHG-001, TST-SEN-003 | Decision versions before and after revocation |
| No authoritative current grants = no retrieval | CTL-004 | SEC-007, NFR-003 | `policy_decision.py`, `reason_codes.py` | — | Query function, before the gateway | Uniform failure; outcome `REFUSED_AUTHORIZATION_UNAVAILABLE` or `REFUSED_NO_ACTIVE_EMPLOYMENT` | Audit outcome and `failing_control`; `tiers_called` empty | TST-SEC-005, TST-SEC-006 | Audit items showing zero tier calls; response comparison |
| Only the gateway can search | CTL-005 | SEC-009, SEC-013 | IAM roles and bucket policies in `infrastructure/template.yaml` | Template | `Retrieve` permission on both knowledge-base ARNs held only by the query role; section buckets readable only by their own tier's knowledge-base role | Access denied | Denied-call results in harness | TST-SEC-004 | `TST-SEC-004.json` (per-principal attempts and outcomes) |
| Labels from the classification record | CTL-006 | DATA-002 | `app/ingestion/handler.py` | Classification store record | Ingestion function | Record unreadable → document not ingested, quarantine record | Quarantine records | TST-DATA-003 | Chunk inventory showing D-14 as CONFIDENTIAL BID-ORION |
| Quarantine invalid classification | CTL-007 | DATA-001, DATA-005, SEC-007 | `app/core/classification.py` | Taxonomy (exact values) | Ingestion function | Section or document excluded and reported | `quarantine-report.json` | TST-DATA-001, TST-DATA-002 | Inventory absence of D-09, D-10, D-11, D-15 canaries; quarantine report |
| Section-bounded objects and effective label | CTL-008 | DATA-003, DATA-007, FUN-004 | `app/core/sections.py`, `app/ingestion/handler.py` | Classification record (document + section marks) | Ingestion function; one custom document per section | Section without valid effective label → excluded | Chunk provenance in inventory | TST-ELG-004, TST-DATA-005, TST-SEN-002 | `inventory.json` (every chunk: document, section, label, scope, version) |
| Special-category exclusion | CTL-009 | DATA-004, CMP-001 | `app/core/sections.py` | Special-category mark on the record | Ingestion function, before any object write or service call | Marked section never leaves ingestion | Exclusion count in ingestion report | TST-DATA-004 | Canary scan of both tiers' vector metadata, audit and logs |
| Tier routing | CTL-010 | SEC-013, DATA-006 | `app/ingestion/tier_router.py` | Effective label | Ingestion function | Unknown label → excluded | Tier inventory | TST-DATA-006 | `inventory.json` per tier |
| Shared-tier eligibility constraint | CTL-011 | SEC-001, SEC-004, FUN-001, FUN-002 | `app/core/constraints.py`, `app/query/retrieval_gateway.py` | Decision | `Retrieve` filter on the shared knowledge base, evaluated during search | Cannot build → CTL-013 | `constraints[]` hash and bytes; retrieved list | TST-ELG-001–005, TST-ELG-009, TST-SEN-001 | Retrieved lists per persona; canary scan |
| Restricted-tier case constraint | CTL-012 | SEC-001, SEC-006, FUN-002 | `constraints.py`, `retrieval_gateway.py` | Decision (cases) | `Retrieve` filter on the restricted knowledge base; tier called only if cases exist | No cases → tier not called | `tiers_called`; retrieved list | TST-ELG-006, TST-ELG-007, TST-ELG-009 | Tier-call records; canary scan |
| Complete constraint or nothing | CTL-013 | SEC-004, SEC-005, NFR-002 | `constraints.py` (positive operators only; size check against an 8,192-byte budget below the observed limits), `retrieval_gateway.py` | Decision; measured platform limit | Query function, before `Retrieve` | Over-size or incomplete → refuse `REFUSED_CONSTRAINT_INCOMPLETE`; never truncate | Outcome; constraint bytes | TST-SEC-003, TST-SCALE-001; L0 unit tests | Constraint hashes identical under prompt attacks; refusal evidence for the over-limit persona |
| Pre-generation verification | CTL-014 | SEC-001, SEC-008, SEC-011 | `app/core/verification.py`, called in `handler.py` | Classification store (current records and versions); decision | Query function, between retrieval and generation | Any mismatch or store unavailable → withhold all; security event | `verification.*`; outcome `WITHHELD_*` | TST-SEC-007, TST-CHG-002, TST-SEN-001, TST-SEN-002 | Audit items showing mismatches and `generation.invoked = false` |
| Citations from verified chunks | CTL-015 | SEC-001, FUN-001 | `app/query/response.py` | Verification result | Response builder | Unverified reference omitted | Response record | TST-ELG-001, TST-ELG-003 | Citation lists per test |
| Uniform response | CTL-016 | FUN-003 | `response.py` | — | Response builder | One message for no-eligible, withheld and unavailable | Response comparison | TST-ELG-008, TST-SEC-005 | Byte comparison of responses |
| No cache of sensitive answers (no cache at all) | CTL-017 | DATA-006 | Absence of cache modules and resources; `generation.py` sends no cache checkpoint | — | Build and template | — | Template and code inspection | TST-DATA-006; L0/L1 checks | Cache inventory (empty) |
| Content-free audit record | CTL-018 | SEC-012, OPS-002, CMP-002 | `app/core/audit_record.py` | Schema | Query function | Record fails schema → still written with `incomplete = true`; never with content | Audit store | TST-OBS-001 | `audit.jsonl`; canary scan |
| Content-free operational logging | CTL-019 | SEC-012, DATA-006 | Logging configuration; structured logger | Template and logger | All functions and API access log | — | CloudWatch Logs | TST-OBS-001 | Log canary scan |
| Decision reconstruction and reports | CTL-020 | OPS-001, OPS-002 | `06-validation/harness/evidence.py` | Audit items and stored record versions | Harness (after run) | Missing version → reconstruction flagged incomplete | Reconstruction report | TST-OBS-002 | `reconstruction.json`; quarantine and mismatch reports |

**Implementation rules that sit inside the controls** (from SPK-E02-A):
1. **Positive operators only.** The constraint builder may emit `equals`, `in`, `andAll`, `orAll`; an L0 test fails if
   `notEquals` or `notIn` appears (C9).
2. **Two constraint shapes on the shared tier.** With no domains, `equals(label, INTERNAL)`; otherwise the `orAll` form,
   because `orAll` needs at least two members.
3. **Size check before the call:** at most 8,192 serialised bytes per constraint, below both observed limits (15,360 and 10,240 bytes); refuse above it (C6; build re-measurement).
4. **Exact label values:** ingestion rejects non-canonical labels (C10).
5. **An empty retrieval result means nothing eligible** (C8), and is handled by the uniform response.
