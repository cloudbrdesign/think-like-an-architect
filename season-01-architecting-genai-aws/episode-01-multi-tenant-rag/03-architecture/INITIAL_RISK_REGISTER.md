# Initial Risk Register and Threat-Model Inputs — Veltamere Document Assistant

**None of these risks is mitigated yet.** No architecture has been chosen. Concern levels are an initial judgement for
prioritising analysis, not measured likelihoods.

## 1. Risk register

| Risk | Description | Consequence | Concern | Requirements / decision areas | Validation idea |
|---|---|---|---|---|---|
| RSK-01 | Cross-tenant retrieval through a shared retrieval path | One competitor sees another's contracts, rates or incidents; contract breach and customer loss | High | SEC-001, SEC-004, DATA-002 · DQ-A, DQ-E | TST-ISO-003, TST-ISO-004, TST-SEN-011 |
| RSK-02 | Forged or substituted tenant context — the caller supplies or alters a tenant identifier (the pattern already exists in the legacy export endpoint) | A user reads any tenant's documents by naming it | High | SEC-003 · DQ-B, DQ-C | TST-SEC-005 |
| RSK-03 | Fail-open when the tenant constraint is missing or empty — an unconstrained retrieval returns every tenant's content | A single missing value exposes all tenants at once | High | SEC-008 · DQ-C, DQ-E | TST-SEC-013 |
| RSK-04 | Mislabelled ingestion — a document is attributed to the wrong tenant | A correct retrieval boundary enforces the wrong owner; the document reaches the wrong customer | High | SEC-006, DATA-003 · DQ-D | TST-ASM-010, TST-SEC-019 |
| RSK-05 | A user's question instructs the assistant to use another tenant's documents | Exposure if isolation relies on instructions to the model | Medium (High if isolation depends on instructions) | SEC-005 · DQ-E | TST-SEC-006 |
| RSK-06 | Indirect prompt injection — text inside a tenant's own document instructs the assistant to reveal other information | Exposure or misleading answers triggered by document content | Medium | SEC-005 · DQ-E | TST-SEC-008 |
| RSK-07 | A bypass path — a debug endpoint, support tool or over-privileged credential reaches documents or retrieval data without the authorisation decision | The boundary exists but can be walked around | High | SEC-009, SEC-010 · DQ-C | TST-SEC-009 |
| RSK-08 | Privileged or support access is used to view tenant content outside an authorised, recorded case | Insider exposure; loss of customer trust | Medium | SEC-009, SEC-010, OPS-001 · DQ-C, DQ-F | review, TST-OPS-015 |
| RSK-09 | Configuration drift as tenants are added — hand-written per-tenant rules are missed or wrong | New tenants are silently unprotected or misconfigured | Medium | NFR-002, OPS-005 · DQ-A | TST-OPS-017, TST-OPS-018 |
| RSK-10 | Logging gaps — an exposure cannot be investigated, or proven not to have happened | Unable to meet notification duties or answer a customer | Medium | OPS-001 · DQ-F | TST-OPS-015 |
| RSK-11 | Logs, caches or other side channels become a leakage path (full content in logs; cached results shared across tenants) | Exposure outside the main retrieval path | Medium | OPS-002, DATA-002 · DQ-E, DQ-F | review, TST-ISO-003, TST-ISO-004 |
| RSK-12 | Stale derived data stays retrievable after a document is deleted or a tenant disables the assistant | Content the customer removed keeps appearing | Medium | FUN-003, BUS-001 · DQ-D, DQ-E | TST-DATA-014, TST-DATA-016 |
| RSK-13 | Cost explosion — per-tenant infrastructure multiplies with tenant count, or a learner leaves resources running | Product becomes unprofitable; learners are billed unexpectedly | Medium | NFR-004, CON-008, OPS-004 · DQ-A | TST-OPS-012; dated cost estimate during architecture |
| RSK-14 | Isolation tests pass vacuously — a cross-tenant test asks for content that would not have been retrieved anyway | False confidence; the boundary is never actually exercised | High (for evidence) | SEC-001 · validation design | Cross-tenant questions target content known to exist; TST-SEN-011 |
| RSK-15 | Citations or source metadata disclose another tenant's document even when the answer text does not | Exposure through the part of the answer users trust most | Medium | SEC-001 · DQ-E | TST-ISO-003, TST-ISO-004 (every output channel) |

## 2. Threat-model inputs for the architecture stage

These inputs are for the threat model produced during architecture. Mitigations are **not** selected here.

**Assets:** tenant documents · everything derived from them for retrieval · generated answers and citations · tenant
context and tenant membership · access-decision records.

**Actors:** a legitimate user of one tenant · a malicious user of one tenant trying to reach another · a user of a tenant
with the assistant disabled · an unauthenticated caller · a user belonging to more than one tenant · Veltamere support
staff · an author of a document containing hostile instructions · a defective or misconfigured platform component.

**Entry points:** asking a question · uploading a document · deleting a document · enabling or disabling the assistant for
a tenant · administrative and support functions · any interface that reaches document or retrieval data directly.

**Trust assumptions to examine:** the identity provider's token contents and membership accuracy (ASM-004, ASM-005) ·
which component asserts tenant context · which component assigns document ownership · which component decides
authorisation · whether any component can retrieve without that decision.

**Attack paths the threat model must cover** (each already has an acceptance test intent):

| Attack path | Acceptance test intent |
|---|---|
| Forged or substituted tenant identifier in any caller-controlled field | TST-SEC-005 |
| A question instructing the assistant to use another tenant's documents | TST-SEC-006 |
| An unauthenticated request | TST-SEC-007 |
| Hostile instructions inside a tenant's own document (indirect prompt injection) | TST-SEC-008 |
| A path that reaches retrieval or documents without the authorisation decision | TST-SEC-009 |
| A document attributed to the wrong tenant, or an upload that tries to choose its tenant | TST-ASM-010, TST-SEC-019 |
| Missing, malformed or unresolvable tenant context | TST-SEC-013 |
| Changing a document's ownership after ingestion | TST-SEC-020 |
| Retrieval of a deleted document or a disabled tenant's documents | TST-DATA-014, TST-DATA-016 |
