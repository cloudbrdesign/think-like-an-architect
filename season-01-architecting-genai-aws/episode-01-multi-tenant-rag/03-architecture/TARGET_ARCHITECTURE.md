# Target Architecture — Veltamere Document Assistant

**Stage:** architecture (E2) · **Status:** accepted — architecture approved 2026-09-14 · **Date:** 2026-09-14

This description is **service-neutral**: it names architectural components and the decisions that shape them. The
mapping to an implementation environment is in [AWS_SERVICE_MAPPING.md](AWS_SERVICE_MAPPING.md).

```
IDENTITY → AUTHORISATION → RETRIEVAL BOUNDARY
verified token → trusted tenant context → authoritative decision → mandatory tenant constraint inside the search
```

## 1. Summary

One shared platform serves every enabled tenant from **one shared retrieval structure** in which every chunk carries its
owning tenant (ADR-001).
- **Tenant context** comes only from a verified token claim, validated against the tenant registry (ADR-002).
- **The retrieval gateway** — the only component allowed to retrieve — makes the authoritative decision and builds a
  mandatory single-tenant constraint that the retrieval structure evaluates **during** the search (ADR-003, ADR-005).
- **Results are verified** against the authoritative ownership record before any content reaches the model. Generation
  runs in-region with a bounded context (ADR-007).
- **Ownership** is assigned once, by the ingestion service, from the uploader's verified tenant (ADR-004).
- **Every request** produces a content-free security audit record (ADR-006).

## 2. Components

| Component | Responsibility | Trust | Holds tenant content? | Decisions |
|---|---|---|---|---|
| End user and client application | Asks questions, uploads and deletes documents | **Untrusted** | Displays own tenant's answers | — |
| Identity provider (existing, authoritative) | Authenticates users; issues signed tokens with subject and one active tenant membership | Trusted external authority | No | ADR-002 |
| API edge | Verifies tokens on every route; the only entry to the services | Trusted | No | ADR-002, ADR-003 |
| Query service — **Tenant Context Resolver** | Builds tenant context from verified claims + registry | Trusted — **trust transition point** | No | ADR-002 |
| Query service — **Retrieval gateway** | Authoritative decision; builds the tenant constraint; sole retrieval caller; verifies results; composes citations; invokes the model | Trusted — **primary enforcement point** | Transiently (verified chunks) | ADR-003, ADR-005, ADR-007 |
| Ingestion service (with the same resolver) | Upload, open and delete documents; assigns ownership; consistency gate; sole indexing caller | Trusted — **write-path enforcement point** | Transiently | ADR-004 |
| Tenant registry | Tenant existence and assistant status (`ENABLED`/`DISABLED`) | Trusted data; written only by onboarding workflow | No | ADR-002 |
| Ownership records | `document_id` → owner, uploader, time, status | Trusted data; written only by ingestion service | No (titles only) | ADR-004 |
| Document store | Original files at `tenants/<tenant_id>/documents/<document_id>` | Trusted storage | **Yes** | ADR-001, ADR-004 |
| Shared retrieval structure and indexing pipeline | Chunks, embeddings and attributes; evaluates constraints during search | Trusted to execute constraints; not trusted to decide | **Yes (derived)** | ADR-001, ADR-005 |
| Generation model | Produces answers from the bounded context | Trusted to process, **not** trusted as a control; receives only verified context | Transiently | ADR-007 |
| Security audit store | Content-free record per request; security role read access | Trusted; sensitive metadata | No | ADR-006 |
| Operational logs | Service health; no bodies or content | Trusted | No | ADR-006 |
| Operator (privileged) access | Attribution correction, investigation; separate role; recorded | Privileged | Can reach content — see section 7 | ADR-003 |

## 3. Trust boundaries

See the diagram [where-does-untrusted-tenant-input-become-trusted-context](diagrams/where-does-untrusted-tenant-input-become-trusted-context.drawio.svg).

| Boundary | Between | What changes across it | Enforced by |
|---|---|---|---|
| TB-1 | Client → API edge | **Identity:** an untrusted request becomes a request with a verified token | CTL-003 |
| TB-2 | API edge → query/ingestion services | **Authority to invoke:** only the edge can invoke the services and supply verified claims | CTL-009 |
| TB-3 | Verified claims → tenant context | **Tenant context:** untrusted request data is discarded; a trusted tenant context is created from claims + registry | CTL-004, CTL-005 |
| TB-4 | Gateway → retrieval structure — **the retrieval boundary** | **Data classification:** from "any tenant's content" to "only this tenant's content" | CTL-007, CTL-008, CTL-015 |
| TB-5 | Retrieval results → generation model | **Content trust:** retrieved text is verified for ownership, then passed as untrusted document content | CTL-017, CTL-022, CTL-023 |
| TB-6 | Ingestion service → document store and retrieval structure | **Ownership:** a file becomes a tenant-owned document with an authoritative record | CTL-011, CTL-012, CTL-013 |
| TB-7 | Services → security audit store and logs | **Data classification:** events leave the request path without content | CTL-019, CTL-020 |
| TB-8 | Operator role → stores | **Privilege:** administrative access outside tenant-facing paths | CTL-010, CTL-021 |

### Where untrusted input becomes trusted context — the life of `tenant_id`

| Stage | Form of tenant identifier | Trusted? | What happens |
|---|---|---|---|
| Request path, query, header, body field or question text | Anything the caller writes | **Never** | Body fields outside the schema are refused; other locations are never read for tenant |
| Identity provider membership | Administrator-controlled membership | Trusted source (CON-004) | The identity provider signs it into the token |
| Token claim, before verification | Claim in a presented token | **Not yet** | The API edge verifies signature, issuer, audience, expiry and scope |
| Verified claim | Claim in the edge's verified claim set | Trusted **as an assertion** | The resolver requires exactly one value |
| Tenant context | `{tenant_id, user_id}` after registry validation | **Trusted** | The only input the gateway and ingestion service accept |
| Retrieval constraint | `owning_tenant EQUALS tenant_id` | Trusted, derived | Evaluated inside the search |
| Owning-tenant attribute on chunks | Supplied by the ingestion service at indexing | Trusted, derived | Cross-checked against ownership records at retrieval |

## 4. Data flows

Step numbers match the diagrams and the threat model.

### A. Query path

Diagram: [how-is-a-question-authorised-before-anything-is-retrieved](diagrams/how-is-a-question-authorised-before-anything-is-retrieved.drawio.svg)

| Step | What happens | Identity / tenant context | Enforced here | Recorded |
|---|---|---|---|---|
| Q1 | Client sends `question` with an access token | Untrusted | — | — |
| Q2 | API edge verifies the token | Verified identity | CTL-003 — failure: refused, no service runs | Edge rejection record |
| Q3 | Edge invokes the query service with the verified claim set; the body schema is checked | Verified claims | CTL-009, CTL-004 — extra fields refused | Audit (`REQUEST_FIELD_REJECTED`) |
| Q4 | Resolver extracts subject and exactly one tenant value | Claims → candidate context | CTL-004 | Audit on failure |
| Q5 | Resolver validates tenant exists and is `ENABLED` | **Trusted tenant context** | CTL-005 — unknown, disabled or unreachable → deny | Audit |
| Q6 | Gateway decides `ALLOW`/`DENY` for `ask` | Tenant context | **CTL-007 (authoritative)** | Audit (decision, reason) |
| Q7 | Gateway builds `owning_tenant EQUALS tenant_id` | Derived constraint | **CTL-015** — cannot build → deny | Audit (`constraint_applied`) |
| Q8 | Gateway calls retrieval with the constraint; question text is only the semantic query | — | **Retrieval boundary** — constraint evaluated during search; CTL-008, CTL-016 | Platform activity record |
| Q9 | Retrieval returns chunks with owner attribute and document identifier | Tenant-scoped data | — | Audit (`retrieved`: IDs + owners) |
| Q10 | Gateway verifies every owner attribute and ownership record (`AVAILABLE`) | — | CTL-017 — mismatch withholds the response | Audit (`verification_outcome`) |
| Q11 | Gateway invokes the in-region model with fixed instructions, question and verified chunks only | — | CTL-022, CTL-023 | — (no content) |
| Q12 | Gateway maps citations to verified documents and returns the answer | — | CTL-018 | Audit (`cited_document_ids`, outcome) |

### B. Document ingestion path

Diagram: [how-does-a-document-get-its-owning-tenant](diagrams/how-does-a-document-get-its-owning-tenant.drawio.svg)

| Step | What happens | Identity / tenant context | Enforced here | Recorded |
|---|---|---|---|---|
| I1 | Client uploads a file and title with an access token | Untrusted | — | — |
| I2 | API edge verifies the token | Verified identity | CTL-003 | Edge rejection record |
| I3 | Ingestion service checks the body schema; any owner, tenant or document identifier field is refused | Verified claims | CTL-004, CTL-011 | Audit (`REQUEST_FIELD_REJECTED`) |
| I4 | Resolver builds tenant context (registry: `ENABLED`) | **Trusted tenant context** | CTL-004, CTL-005 | Audit on failure |
| I5 | Service generates `document_id` and derives location `tenants/<tenant_id>/documents/<document_id>` | Derived from context | CTL-011 | — |
| I6 | Service writes ownership record: owner, uploader, time, status `RECEIVED` | Authoritative ownership | CTL-011 | Ownership record |
| I7 | Service stores the original at the derived location | — | — | — |
| I8 | Consistency gate: record owner = location tenant = indexing owner; tenant `ENABLED` | — | **CTL-012** — otherwise `QUARANTINED`, not indexed | Audit (`ATTRIBUTION_INCONSISTENT`) |
| I9 | Service submits the document for indexing, supplying owner and `document_id` attributes itself | — | CTL-011, CTL-013 (exclusive indexing permission) | Platform activity record |
| I10 | Indexing pipeline parses, chunks and embeds; every chunk inherits the attributes | Derived data inherits owner | CTL-001 | — |
| I11 | Status becomes `AVAILABLE` when indexing confirms | — | — | Ownership record; audit |

### C. Document deletion and tenant disablement

| Step | What happens | Enforced here | Recorded |
|---|---|---|---|
| D1 | Client requests deletion of `document_id` with a token | — | — |
| D2 | Edge verifies token; resolver builds tenant context | CTL-003, CTL-004, CTL-005 | Audit on failure |
| D3 | Service loads the ownership record; owner ≠ tenant context → **not found** | CTL-014 | Audit (`NOT_FOUND_FOR_TENANT`) |
| D4 | Status → `DELETING`. From this moment retrieval verification discards the document's chunks | CTL-014, CTL-017 | Ownership record; audit |
| D5 | Service removes the document from the retrieval structure | CTL-013 | Platform activity record |
| D6 | Service deletes the original from the document store | CTL-014 | — |
| D7 | Status → `DELETED` when both removals are confirmed; removal completes within the agreed window (ASM-008) | CTL-014 | Ownership record; audit |
| T1 | Onboarding workflow sets tenant registry status `DISABLED` | Registry write restricted to onboarding | Registry change record |
| T2 | Every subsequent query and upload for that tenant is denied, whatever tokens remain valid | CTL-005 | Audit (`TENANT_DISABLED`) |
| T3 | Indexed documents remain unreachable: no enabled tenant context can carry that tenant's identifier | CTL-005, CTL-015 | — |
| T4 | Purging a departed tenant's documents and derived data follows D4–D7 for each document (full offboarding design is Episode 03) | CTL-014 | Audit |

## 5. Data inventory and classification

Derived data is classified **at least as high as its source**. Detailed classification of personal and sensitive
information is Episode 02; here every tenant document is confidential tenant data.

| Data | Location | How the owning tenant is carried | Classification |
|---|---|---|---|
| Original documents | Document store | Location prefix + ownership record | Confidential tenant data |
| Chunks, embeddings | Shared retrieval structure | Owning-tenant attribute on every chunk (CTL-001) | Confidential tenant data (derived) |
| Ownership records | Ownership records store | Owner field (authoritative) | Confidential metadata (titles) |
| Tenant registry | Registry store | Is the tenant | Internal |
| Model context and answers | Transient in gateway and model | Built only from one tenant's verified chunks | Confidential tenant data (derived) |
| Security audit records | Audit store | `tenant_context` field | Sensitive internal metadata (no content) |
| Operational logs | Log store | None needed | Internal (no content) |
| Tokens | Transient | Membership claim | Credential — never logged |

## 6. Fail-closed design

The approved requirement is **FAIL CLOSED** (SEC-008). "Closed" means: no retrieval, no generation, a recorded event.

| Condition | Detected by | Behaviour | Client sees | Recorded |
|---|---|---|---|---|
| Token missing | API edge | Request refused before any service runs | Unauthenticated error | Edge rejection |
| Token invalid (signature, issuer, audience, expiry, not-before, scope) | API edge | Refused | Unauthenticated error | Edge rejection |
| Identity token presented instead of access token | API edge (scope) / resolver (token use) | Refused | Unauthenticated / forbidden | Edge / audit |
| Tenant claim missing | Resolver | Deny | Forbidden | `TENANT_CLAIM_MISSING` |
| Several tenant values | Resolver | Deny — never pick one | Forbidden | `TENANT_CLAIM_AMBIGUOUS` |
| Tenant unknown to registry | Resolver | Deny | Forbidden | `TENANT_UNKNOWN` |
| Tenant disabled | Resolver | Deny (query and upload) | Forbidden | `TENANT_DISABLED` |
| Registry lookup fails or times out | Resolver | Deny — no "allow if unavailable" | Retryable unavailable | `REGISTRY_UNAVAILABLE` |
| Authorisation component unavailable | The decision is in-process in the gateway; if the query service is unavailable, no answers are produced and the rest of the platform is unaffected (NFR-003) | No retrieval | Retryable unavailable | Edge / platform health |
| Request carries an undocumented field (including a tenant field) | Query or ingestion service | Refused | Client error | `REQUEST_FIELD_REJECTED` |
| Retrieval constraint cannot be constructed | Constraint builder | Deny — no retrieval call exists without a constraint | Forbidden | `CONSTRAINT_UNBUILDABLE` |
| A retrieved result lacks the owner attribute, or its owner ≠ tenant context | Gateway verification | Withhold entire response | Generic error | `OWNERSHIP_MISMATCH` (security event) |
| Ownership record lookup fails during verification | Gateway verification | Withhold entire response | Retryable unavailable | `REGISTRY_UNAVAILABLE` |
| A result's document status is not `AVAILABLE` | Gateway verification | Discard that result; continue | Answer from remaining results | `DISCARDED:n` |
| Document tenant metadata missing at ingestion | Consistency gate | `QUARANTINED`, not indexed | Upload failed | `ATTRIBUTION_INCONSISTENT` |
| Document tenant metadata invalid or conflicting (record ≠ location ≠ indexing owner) | Consistency gate | `QUARANTINED`, not indexed | Upload failed | `ATTRIBUTION_INCONSISTENT` |
| Security audit record cannot be written | Gateway / ingestion service | Refuse the request before generation (**ASSUMPTION:** acceptable for the pilot; availability trade-offs are Episode 07) | Retryable unavailable | Operational alarm |

## 7. Bypass analysis

**Rule:** there is no "secure path" alongside a path that avoids tenant authorisation. Every path that can reach
retrieval data or documents is listed here.

### Authorised paths

| Path | Passes | Trust assumptions |
|---|---|---|
| Ask a question | Edge → resolver → gateway decision → constraint → verification | Identity provider membership is correct (ASM-005) |
| Upload a document | Edge → resolver → ingestion attribution → consistency gate | As above; ASM-006 (only this upload path in the pilot) |
| Open a cited document | Edge → resolver → ownership record check (CTL-014) | Citation links always point to this route, never to storage or the legacy endpoint |
| Delete a document | Edge → resolver → ownership record check → removal | As above |

### Prohibited paths

| Path | Why it is prohibited | Prevented by | Detected by | Test |
|---|---|---|---|---|
| Invoking the query or ingestion service directly with a forged claim set | Would bypass token verification (TB-2) | CTL-009 | Audit gaps; platform activity | TST-SEC-009, TST-SEC-023 |
| Any component other than the gateway calling retrieval | The retrieval permission cannot be scoped to one tenant | CTL-008 | CTL-021 | TST-SEC-009, TST-SEC-023 |
| Querying the underlying vector data directly | Skips the retrieval structure's constraint handling entirely | CTL-008 (only the indexing service may) | CTL-021 | TST-SEC-023 |
| Reading the document store directly (users, client applications, other platform services) | Originals are tenant content | Storage access limited to the ingestion service and indexing pipeline | Platform activity | TST-SEC-009 |
| **Legacy export endpoint** reading assistant documents or retrieval data | It trusts a request-supplied tenant identifier | It has no permission on the assistant's stores; citation links never use it | Platform activity | TST-SEC-009; RR-07 records the endpoint itself |
| Debug endpoint or "tenant override" parameter | A switch that disables isolation is itself a bypass | None exists; request schema refuses extra fields | Audit (`REQUEST_FIELD_REJECTED`) | TST-SEC-005, TST-SEC-009 |
| Admin endpoint in the product | Would create a user-reachable privileged path | None exists; privileged work uses the operator role only | CTL-021, audit | TST-SEC-009 |
| Batch or bulk import jobs | Would need their own attribution (ASM-006) | Not permitted in the pilot; any future import must call the ingestion service | CTL-021 | Review |
| Other internal services calling the gateway's retrieval module | Would reuse the gateway without the resolver | The module is internal to the query service; the retrieval client accepts only a tenant-scoped query from the decision function | Code review | TST-SEC-013 |
| Model tools or model-driven retrieval | Would move scope decisions to the model | CTL-016, CTL-022 | — | TST-SEC-006, TST-SEC-008 |

### Privileged paths

| Path | Trusted for | Controls | Residual |
|---|---|---|---|
| Indexing pipeline (platform-managed) | Reading originals and writing chunks with the attributes supplied | Its identity may read only the document store and write only the retrieval structure | RR-05 |
| Operator role | Attribution correction; incident investigation | CTL-010: separate role, not reachable from tenant routes, every use recorded | RR-02 |
| Infrastructure and deployment administrators | Changing permissions and configuration | Change review; permission exclusivity checked repeatedly (TST-SEC-023) | RR-02, RR-06 |
| Identity provider administrators | Membership | Customer administrators' membership reviews (ASM-005) | RR-01 |
| Onboarding workflow | Writing the tenant registry | Only this workflow may write the registry | RR-06 |

## 8. Citation isolation

Citations are treated as **data disclosure**. A design that keeps another tenant's text out of the answer, but shows that
tenant's document name, storage location, metadata or citation text, still violates SEC-001.

- **Retrieval design:** citations are built only from results that passed ownership verification (CTL-017, CTL-018).
- **What a citation contains:** `document_id`, the tenant's own document title from the ownership record, and a location
  within the document when available. Never a storage path, index identifier, score or raw attribute set.
- **Model output:** references are mapped to the verified set; anything unmapped is removed.
- **Links:** a citation link opens the document through the ownership-checked route (CTL-014).
- **Threat model:** THR-13. **Validation:** TST-SEC-021, TST-ISO-003, TST-ISO-004.
- **Logging:** only `cited_document_ids` are recorded; titles and text are not.

## 9. Observability

Designed in ADR-006. **Security audit data** (who, which tenant, what decision, which constraint, which documents,
what outcome) is separated from **content and application data** (questions, chunks, answers), which is never logged.
- Audit records are read by the security role only.
- Operational logs support service health without bodies.
- Platform activity records are used to detect retrieval by any identity other than the gateway (CTL-021).

## 10. Evolution: shared content

**Baseline (ASM-007): no shared content.** Episode 01 does not implement any of the following. This section shows that
the chosen model can evolve **without weakening the current guarantee**. The rule that must survive every evolution:

> The retrieval constraint is built **only** from server-side authorisation state. It is never widened with a value the
> caller or the model can influence, and "shared" content never lives in the tenant partition with a special value that
> an `OR` could reach.

| Future requirement | What would change | How the guarantee is preserved | Requirements affected |
|---|---|---|---|
| Global documentation for all tenants (for example platform user guides) | A **separate** retrieval structure for global content, queried with no tenant constraint and merged in the gateway, with provenance labels in citations | Tenant partitions are untouched; global content contains no tenant data by definition, checked at its own ingestion | ASM-007 revised; new requirement defining "global" content and who may publish it |
| Content shared between selected tenants | Explicit, recorded **sharing grants**; the gateway builds `owning_tenant IN [own tenant, grant sources]` from grant records only | The list comes from server-side grant records, never from the request. Every grant is auditable and revocable. The negative tests gain "grant revoked" cases | SEC-001 gains an **authorised** cross-tenant case; new ADR; likely a policy decision point (ADR-003 trigger) |
| Public content | Separate structure as for global content; never mixed with tenant partitions | Same as global | ASM-007 revised |
| Administrator-only content within a tenant | A second attribute (audience) and a role claim; constraint `owning_tenant EQUALS t AND audience IN [roles]` | The tenant term stays mandatory; roles come from verified claims | New role requirement; ADR-002 extended |

## 11. What is trusted — and what breaks isolation on its own

Answering the E1 cross-cutting question "which trusted component, if wrong, breaks isolation on its own?":

| Trusted element | If it is wrong | What still catches or limits it |
|---|---|---|
| Identity provider membership | A user acts for the wrong tenant — **breaks isolation for that user on its own** | Customer membership reviews; audit shows every retrieval (RR-01) |
| Tenant Context Resolver | Wrong tenant context | The constraint and verification both use the same context, so verification cannot catch this; TST-SEC-005 and code review guard it |
| Constraint builder (CTL-015) | Missing or wrong constraint | Verification (CTL-017) withholds the response; TST-SEN-011 proves the tests detect it |
| Ingestion attribution (CTL-011) | Wrong owner, consistently recorded — **served to the wrong tenant on its own** | Ownership record and audit make it investigable (RR-03) |
| Permission exclusivity (CTL-008, CTL-013) | Another component can retrieve or index freely | Bypass detection (CTL-021); TST-SEC-023 |
| Retrieval structure's constraint evaluation | Returns non-matching chunks | Verification (CTL-017) detects and withholds (RR-05) |

## 12. Diagrams

| Diagram | Question it answers |
|---|---|
| [where-does-untrusted-tenant-input-become-trusted-context.drawio.svg](diagrams/where-does-untrusted-tenant-input-become-trusted-context.drawio.svg) | Where are the trust boundaries, and where does untrusted input become trusted tenant context? |
| [how-is-a-question-authorised-before-anything-is-retrieved.drawio.svg](diagrams/how-is-a-question-authorised-before-anything-is-retrieved.drawio.svg) | In what order are identity, authorisation, retrieval constraint and verification applied to a question? |
| [how-does-a-document-get-its-owning-tenant.drawio.svg](diagrams/how-does-a-document-get-its-owning-tenant.drawio.svg) | Who assigns ownership, and what happens when attribution is inconsistent? |

Diagrams are draw.io files in the editable `.drawio.svg` format. Open them in diagrams.net to edit.
