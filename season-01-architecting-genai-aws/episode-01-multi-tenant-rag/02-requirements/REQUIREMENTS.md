<!-- template: tla-requirements/1 -->
# Requirements — Veltamere Document Assistant

**Rules for this set**
- Requirements state **what** must be true, never **which service** provides it.
- IDs are stable. `Source` names the business objective (OBJ-n), stakeholder or constraint that created the requirement.
- `Verified by` names acceptance test intents in [ACCEPTANCE_TEST_INTENT.md](../06-validation/ACCEPTANCE_TEST_INTENT.md),
  or `review` where a test is not the right proof.
- `Related decisions` names decision questions in
  [ARCHITECTURE_DECISION_QUESTIONS.md](../04-decisions/ARCHITECTURE_DECISION_QUESTIONS.md), as they stood when the
  requirements were approved. The decisions that answer them (ADRs) and the controls they introduce are traced in the
  [traceability matrix](../06-validation/TRACEABILITY_MATRIX.md).
- **Invariants.** Requirements marked **INVARIANT** state a security property the system must hold at all times. Absolute
  words such as "never" express the invariant; they are not a claim that the property is automatically guaranteed. Each
  invariant is later validated against the identified attack paths, including tests that are shown capable of failing.
- In this episode there is **no authorised cross-tenant retrieval use case**.

## Business

| ID | Requirement | Rationale | Priority | Source | Verified by | Related decisions |
|---|---|---|---|---|---|---|
| BUS-001 | The assistant can be enabled or disabled per tenant. A disabled tenant's documents are not processed for retrieval and are never retrieved | Customers must consent before their documents are used to generate answers | MUST | OBJ-2 · Legal | TST-DATA-016 | DQ-D, DQ-E |
| BUS-002 | Enabling a tenant follows a repeatable, documented procedure | Onboarding must not become a bespoke project | SHOULD | OBJ-2 · Product | TST-OPS-017 | DQ-A |

## Functional

| ID | Requirement | Rationale | Priority | Source | Verified by | Related decisions |
|---|---|---|---|---|---|---|
| FUN-001 | An authenticated user can ask a natural-language question and receive an answer grounded in their own tenant's documents, with citations to the source documents | The core capability | MUST | OBJ-1 · End users | TST-ISO-001, TST-ISO-002 | DQ-E |
| FUN-002 | A document uploaded by a tenant becomes available to that tenant's users once it has been processed | Answers must reflect the tenant's own content | MUST | OBJ-1 · Customer administrators | TST-ISO-001, TST-ISO-002 | DQ-D |
| FUN-003 | When a tenant deletes a document, the document and anything derived from it stop being retrievable within an agreed window (ASM-008) | Deleted content must not keep appearing in answers; full freshness design is Episode 03 | SHOULD | Customer administrators | TST-DATA-014 | DQ-D, DQ-E |

## Security

| ID | Requirement | Rationale | Priority | Source | Verified by | Related decisions |
|---|---|---|---|---|---|---|
| SEC-001 | **INVARIANT.** A user acting in Tenant A's context never receives information belonging to Tenant B — not in retrieval results, generated answers, citations or source metadata — and the reverse | The central contractual and business risk | MUST | OBJ-3 · Security · Legal | TST-ISO-003, TST-ISO-004, TST-SEN-011 | DQ-A, DQ-E |
| SEC-002 | Every question is attributed to an authenticated identity. An unauthenticated request receives no retrieval and no generated answer | No anonymous access to tenant content | MUST | Security | TST-SEC-007 | DQ-B, DQ-C |
| SEC-003 | **INVARIANT.** The tenant context used for authorisation and retrieval is derived only from the verified identity issued by the trusted identity source. A tenant identifier supplied by the caller — in a path, query, body, header or the question text — is never trusted to select tenant data | Prevents tenant substitution, a pattern already present in the legacy export endpoint | MUST | OBJ-3 · Security | TST-SEC-005 | DQ-B |
| SEC-004 | **INVARIANT.** Authorisation is decided **before** any document content is retrieved, and no content belonging to another tenant enters a query's retrieval results or model context at any stage. Removing such content afterwards does **not** satisfy this requirement | Content that has been retrieved has already crossed the boundary | MUST | OBJ-3 · Security | TST-ISO-003, TST-ISO-004, TST-SEN-011 | DQ-C, DQ-E |
| SEC-005 | **INVARIANT.** Instructions in a user's question or inside document content cannot widen the tenant scope of retrieval. Isolation never depends on a model following instructions | Models can be persuaded; authorisation cannot depend on persuasion | MUST | OBJ-3 · Security | TST-SEC-006, TST-SEC-008 | DQ-E |
| SEC-006 | **INVARIANT.** Every document is attributed to exactly one owning tenant at ingestion, by a trusted part of the system, based on the authenticated uploader's tenant — never on values inside the document or a tenant chosen by the uploader | Retrieval can only be as correct as the ownership it enforces | MUST | OBJ-3 · Customer administrators | TST-SEC-019, TST-ASM-010 | DQ-D |
| SEC-007 | A document's tenant attribution cannot be changed through any user-facing path. Any correction is an explicit, authorised and recorded administrative action | Mutable ownership is an isolation bypass | MUST | Security · Legal | TST-SEC-020 | DQ-D |
| SEC-008 | **INVARIANT.** If the tenant context, authorisation data or a document's attribution is missing, malformed or cannot be resolved, the system returns no retrieval results and records the event (fails closed) | An empty or missing constraint must never mean "everything" | MUST | OBJ-3 · Security | TST-SEC-013 | DQ-B, DQ-C, DQ-E |
| SEC-009 | No route available to tenant users or their client applications reaches document or retrieval data without passing the authorisation decision | A boundary with a side door is not a boundary | MUST | OBJ-3 · Security | TST-SEC-009 | DQ-C |
| SEC-010 | Each component that handles tenant documents holds only the permissions its function needs; no user-facing component holds credentials granting unrestricted access to every tenant's documents | Limits the blast radius of a defect or compromise | MUST | Security | review | DQ-C |
| SEC-011 | Tenant documents and data derived from them are protected as confidential tenant data at rest and in transit | Contractual confidentiality; classification detail is Episode 02 | MUST | Legal · Security | review | DQ-A, DQ-F |

## Data

| ID | Requirement | Rationale | Priority | Source | Verified by | Related decisions |
|---|---|---|---|---|---|---|
| DATA-001 | For every document the system can state its owning tenant, uploader identity, ingestion time and processing status | Ownership must be provable and investigable | MUST | OBJ-4 · Customer administrators | TST-SEC-019 | DQ-D |
| DATA-002 | Everything derived from a document for retrieval (for example extracted text, fragments, indexes, embeddings or cached results) carries or inherits the document's owning tenant, and nothing derived from a document is retrievable outside that tenant | Derived data is still the tenant's data | MUST | OBJ-3 · Security | TST-ISO-003, TST-ISO-004 | DQ-D, DQ-E |
| DATA-003 | A document attributed to the wrong tenant can be detected or corrected, and the consequence of a mis-attribution is understood and stated | Attribution errors are the boundary's weakest input | SHOULD | Security · Customer administrators | TST-ASM-010 | DQ-D |

## Non-functional

| ID | Requirement | Rationale | Priority | Source | Verified by | Related decisions |
|---|---|---|---|---|---|---|
| NFR-001 | For about 90% of questions, the answer begins to appear within about 5 seconds under the assumed load (ASM-003, ASM-007) | Adoption depends on responsiveness; isolation takes precedence over latency | SHOULD | OBJ-1 · End users | review | DQ-A, DQ-E |
| NFR-002 | Adding a tenant requires no code change and no hand-written per-tenant authorisation or retrieval rule | Hand-maintained per-tenant rules drift and fail silently as tenants grow | MUST | OBJ-2 · Platform Engineering · Security | TST-OPS-017 | DQ-A |
| NFR-003 | If the assistant is unavailable, the platform's existing features keep working | The assistant is additive; failure design depth is Episode 07 | SHOULD | Platform Engineering | review | DQ-A |
| NFR-004 | Running cost grows mainly with usage and document volume; adding a tenant does not add large fixed infrastructure cost unless an approved decision justifies it | Pricing assumes shared infrastructure | SHOULD | OBJ-5 · Product | review | DQ-A |

## Operational

| ID | Requirement | Rationale | Priority | Source | Verified by | Related decisions |
|---|---|---|---|---|---|---|
| OPS-001 | Each question produces a record of the authenticated user, the tenant context, the authorisation decision, the identifiers of documents retrieved and the outcome — enough to investigate a suspected exposure | Today searches are not logged at all | MUST | OBJ-4 · Security · Legal | TST-OPS-015 | DQ-F |
| OPS-002 | Records of access decisions do not contain full document content or full answers by default | Logs must not become a second copy of confidential data | SHOULD | Security · Legal | review | DQ-F |
| OPS-003 | The learner implementation deploys non-interactively and reproducibly from the published instructions | Validation must be repeatable by anyone | MUST | CON-007 | TST-OPS-018 | — |
| OPS-004 | Cleanup removes every billable resource created by the learner implementation, and the removal can be verified | Learners must not keep paying after the engagement | MUST | CON-008 | TST-OPS-012 | — |
| OPS-005 | The isolation tests are automated and repeatable, so they can run after any change | Configuration changes can silently break isolation | SHOULD | OBJ-6 · Security | TST-OPS-018 | — |

## Compliance and contractual

| ID | Requirement | Rationale | Priority | Source | Verified by | Related decisions |
|---|---|---|---|---|---|---|
| CMP-001 | Veltamere can demonstrate logical segregation of each customer's data with test results and access records | Customer contracts and annual evidence requests | MUST | OBJ-6 · Legal | TST-ISO-003, TST-ISO-004, TST-OPS-015 | DQ-A, DQ-F |
| CMP-002 | Tenant documents and everything derived from them stay within the contracted hosting region | Contractual region commitment (CON-006) | MUST | Legal | review | DQ-A |
