<!-- template: tla-architecture-review/1 -->
# Architecture Review Questions — Veltamere Document Assistant

The questions an architecture review board or an interviewer should be able to ask you at the end of this engagement.
Answer by citing your artifacts; defending the architecture matters more than recalling facts.

**Updated after the educational implementation (E4).**
- **Question sets:** the engagement and design-specific questions remain. A third set, *Implementation and evidence
  questions*, asks you to defend what you built and what your tests proved.
- **Citing results:** a "result" is your own validation run. The example results are in
  [07-evidence/e4-validation-2026-09-14](07-evidence/e4-validation-2026-09-14/README.md).

## Engagement questions

| Area | Question | A strong answer cites |
|---|---|---|
| Decisions | Which requirement drove your tenant isolation model? | SEC-001, NFR-002, NFR-004, CMP-001; options analysis section 2; ADR-001 |
| Decisions | Why did you choose logical or physical isolation — and what would make you change it? | ADR-001 trade-offs and evolution triggers; ASM-001, ASM-002; COST_AND_SCALE_ANALYSIS |
| Identity | Where is tenant identity trusted, and why is that component trustworthy? | ADR-002 "what must be verified"; trust-boundary diagram; TARGET_ARCHITECTURE section 3 |
| Identity | Why can't a user change their tenant? Show the path a forged tenant identifier takes | SEC-003, CTL-004, CTL-006, THR-01, THR-16, TST-SEC-005 result |
| Authorisation | Where exactly does authorisation occur, and what happens if that component receives no tenant context? | ADR-003 layer table; CTL-007, CTL-015; fail-closed table; TST-SEC-013 result |
| Authorisation | Is there any path to the documents that does not pass authorisation? How do you know? | TARGET_ARCHITECTURE section 7; CTL-008, CTL-009; TST-SEC-009 and TST-SEC-023 results |
| Retrieval | What happens if a user asks the model for another tenant's data — and which control actually stops it? | SEC-005, CTL-015, CTL-016; query flow diagram Q8; TST-SEC-006 result at the retrieval layer |
| Retrieval | Why is removing other tenants' content after retrieval not good enough? | SEC-004; ADR-005 options C and F; why CTL-017 is defence in depth only |
| Data | What happens if ingestion metadata is wrong? Who could make it wrong? | ADR-004 mislabelled-document table; CTL-012, CTL-017; TST-ASM-010 and TST-SEC-022 results |
| Evidence | How do you know your cross-tenant tests are not passing vacuously? | VALIDATION_PLAN section 5; TST-SEN-011 result; RSK-14 |
| Risk | What is the largest residual risk in your design? | RESIDUAL_RISK_REGISTER (RR-01, RR-03, RR-04); threat model section 7 |
| Scale | What fails first as the tenant count grows towards 400? | COST_AND_SCALE_ANALYSIS section 4; RR-13; PC-06 |
| Context change | What would change if the documents were regulated or highly sensitive data? | ADR-001 consequences (one encryption domain); Episode 02 scope; evolution triggers |
| Assurance | How would you prove tenant isolation to a customer's auditor? | CMP-001; ADR-006 audit fields; test results; sensitivity run evidence |
| Production | What would production require beyond the learner implementation? | AWS_SERVICE_MAPPING sections 6 and 7 (teaching simplifications, production pack fit) |

## Design-specific questions

| Area | Question | A strong answer cites |
|---|---|---|
| Isolation model | Why a shared retrieval structure and not per-tenant infrastructure? | ADR-001 "why not A"; CON-002, CON-003, NFR-002, NFR-004, ASM-001; segregation is required, dedicated per-tenant infrastructure is not; blast radius versus resource count, operations and fixed cost; cell or physical isolation as the escalation path |
| Isolation model | A shared structure means one missing filter exposes everyone. Why is that acceptable here? | ADR-001 conditions 1–5; CTL-015 construction; CTL-008; CTL-017; TST-SEN-011; RR-04 |
| Isolation model | Why not cells now, if they limit blast radius? | Options analysis Option C; ADR-001 evolution triggers; the always-filter rule |
| Isolation model | Why not let the store enforce per-user access lists? | Options analysis Option D (fails the onboarding gate); PC-16 "not authorization" |
| Identity | A signed token carries the tenant. Why is that not automatically trustworthy? | ADR-002 context; membership must be administrator-controlled (CTL-006); PC-19, PC-20; THR-16 |
| Identity | Why validate the claim against a registry instead of trusting the token alone? | ADR-002 "why not B alone"; BUS-001; TST-DATA-016 |
| Identity | Why not look up membership on the server instead of using the claim? | ADR-002 "why not C"; CON-004 |
| Authorisation | Why is the decision in the retrieval gateway and not a dedicated policy service? | ADR-003 "why not B" and its adoption trigger |
| Authorisation | The retrieval permission cannot be scoped to one tenant. What does the architecture do about that? | PC-04, PC-05; CTL-008, CTL-021; TST-SEC-023; RR-06 |
| Authorisation | Could someone invoke the query service directly with forged claims? | CTL-009; threat model F-01; VE-07 |
| Ingestion | Why is ownership supplied by the ingestion service rather than a metadata file next to each document? | ADR-004 platform evidence; PC-07, PC-08; threat model F-07 |
| Ingestion | A consultant uploads a competitor's rate card into the wrong tenant. What happens, and who owns that risk? | ADR-004 case (b); RR-03; audit records; correction workflow CTL-013 |
| Retrieval boundary | Why retrieve, verify and then generate, instead of one retrieve-and-generate call? | ADR-007 "why not A"; CTL-017, CTL-018; PC-14 |
| Retrieval boundary | Why is model-generated (implicit) filtering forbidden? | CTL-016; PC-02; SEC-005 |
| Citations | Why are citations treated as data disclosure, and what may a citation contain? | TARGET_ARCHITECTURE section 8; CTL-018; TST-SEC-021 |
| Failure behaviour | The tenant registry is unavailable. What happens, and why is that the right trade-off? | Fail-closed table; SEC-008 over NFR-003; RR-13 |
| Failure behaviour | Why does an ownership mismatch withhold the whole response rather than just the bad result? | ADR-005 decision item 7 |
| Observability | An exposure is suspected. Reconstruct who asked, in which tenant, and what was retrieved — without reading any content | ADR-006 field table; CTL-019, CTL-020; TST-OPS-015 |
| Validation | Why does the sensitivity test observe the retrieval layer and not the answer? | VALIDATION_PLAN section 5; threat model F-08 |
| Residual risk | Which trusted element, if wrong, breaks isolation on its own — and what limits the damage? | TARGET_ARCHITECTURE section 11 |
| Cost | At what point does the shared model stop being attractive? | COST_AND_SCALE_ANALYSIS section 4 |
| Evolution | Product wants "shared documentation for all customers". What must change, and what must not? | TARGET_ARCHITECTURE section 10; RR-12; ASM-007 |
| Production hardening | Which three production changes most reduce residual risk, and which risks do they address? | AWS_SERVICE_MAPPING section 7; RR-02, RR-04, RR-06 |
| Neutrality | Show that the decisions came before the service choices | Options analysis section 9; ADR "platform evidence (checked after the decision)" sections |

## Implementation and evidence questions

| Area | Question | A strong answer cites |
|---|---|---|
| Primary control | Show the one function that builds the tenant filter. What stops any other code path from building a different one? | `05-implementation/app/shared/retrieval_scope.py` (`authorize_and_scope`, the scoped query only it can issue); `retrieval_client.py` type check; component tests `06-validation/tests/test_retrieval_boundary.py` |
| Trusted context | How does a verified group claim become exactly one tenant? What happens with no group, two groups or a malformed claim? | `tenant_claims.py` and platform finding CH-12 (claims arrive as strings); `tenant_context.py`; TST-SEC-013 result |
| Forged tenant | You sent another tenant's ID in the body, query, header, path and question. Which were refused, which were ignored, and how do you know? | TST-SEC-005 result; the audit records' `tenant_context` and `constraint`; `request_schema.py` |
| Bypass | Could someone invoke the query function directly with forged claims, or retrieve with another role? | `infrastructure/template.yaml` resource policies (explicit Deny) and role policies; TST-SEC-009 and TST-SEC-023 results |
| Non-vacuity | Your cross-tenant tests passed. Prove they could have failed | Non-vacuity preconditions in the TST-ISO-003 and TST-ISO-004 evidence; TST-SEN-011 verdict and variant results |
| Observation point | In the sensitivity run every answer was withheld. Why would a test that only checked answers have missed the missing control? | Ownership verification as defence in depth (`ownership_verification.py`); VALIDATION_PLAN section 5; `retrieved` in the variant audit records |
| Ingestion | A caller tries to choose the owner or the storage location of a document. What stops them? | `ownership.py` (server-derived key, attribution gate) and platform finding CH-11; TST-SEC-019, TST-ASM-010 results |
| Audit | Reconstruct a refused cross-tenant attempt from the audit record alone. What does the record deliberately not contain? | `audit.py` field allow-list; TST-OPS-015 result |
| Evidence scope | Which conclusions from your run hold only for your tested conditions, and what would production still need to verify? | The example evidence README's limits; [latency summary](07-evidence/e4-validation-2026-09-14/LATENCY_SUMMARY.md); RESIDUAL_RISK_REGISTER; VE-09 and VE-11 in PLATFORM_VERIFICATION |
| Cleanup | How do you know nothing from the lab remains, given that a tag search can lag behind deletions? | `06-validation/harness/cleanup_check.py` (service-by-service confirmation); TST-OPS-012 result |
