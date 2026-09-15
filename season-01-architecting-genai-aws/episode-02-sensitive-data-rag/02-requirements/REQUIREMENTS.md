<!-- template: tla-requirements/1 -->
# Requirements — Kestrelmoor Knowledge Assistant

**Status:** accepted (2026-09-15).

**Rules for this set**
- **What, not how:** requirements state what must be true, never which service provides it. IDs are stable once
  approved.
- **Source column:** names the objective (OBJ-n in the brief), stakeholder or constraint.
- **Verified by:** names tests in [VALIDATION_PLAN.md](../06-validation/VALIDATION_PLAN.md), or `review`.
- **Related decisions:** names decision questions in
  [ARCHITECTURE_DECISION_QUESTIONS.md](../04-decisions/ARCHITECTURE_DECISION_QUESTIONS.md).
- **INVARIANT:** marks a security property that must hold at all times. "Never" states the invariant; it is not a claim
  that the property is guaranteed. Each invariant is validated against its attack paths, including tests shown able to
  fail.

**Vocabulary** (defined precisely in [AUTHORIZATION_AND_SENSITIVITY_MODEL.md](../03-architecture/AUTHORIZATION_AND_SENSITIVITY_MODEL.md)):
- **identity** — who is asking;
- **entitlement** — an explicit, authoritative grant: active employment, access-domain membership, or case assignment;
- **ownership** — Kestrelmoor owns every document, so ownership decides nothing here;
- **classification** — a section's sensitivity label and scope, assigned by its owner;
- **retrieval eligibility** — whether a given requester may retrieve a given section now.

## Business

| ID | Requirement | Rationale | Priority | Source | Verified by | Related decisions |
|---|---|---|---|---|---|---|
| BUS-001 | Every active employee can use the assistant and receive answers from INTERNAL content without any additional grant | Most of the value is general engineering and procedural knowledge | MUST | OBJ-1 · Product owner | TST-ELG-001 | DQ-A |
| BUS-002 | Data owners grant and revoke access to CONFIDENTIAL and RESTRICTED content through the existing entitlement process, with no change to the assistant | Owners, not engineers, decide who may see their information | MUST | OBJ-5 · Records Manager | TST-CHG-001, review | DQ-A, DQ-E |
| BUS-003 | Adding a new access domain or case type requires configuration in the entitlement and classification sources only | The platform team cannot absorb per-domain engineering | SHOULD | OBJ-5 · Platform team | review | DQ-A, DQ-D |

## Functional

| ID | Requirement | Rationale | Priority | Source | Verified by | Related decisions |
|---|---|---|---|---|---|---|
| FUN-001 | An employee asks a natural-language question and receives an answer grounded only in content they are eligible to retrieve, with citations at section level | The core capability | MUST | OBJ-1 · Employees | TST-ELG-001 | DQ-D, DQ-F |
| FUN-002 | An employee who holds the relevant domain membership or case assignment receives answers that use that CONFIDENTIAL or RESTRICTED content | A control that blocks the entitled is a broken control | MUST | OBJ-1 · Commercial Director · Head of Safety Investigations · HR Director | TST-ELG-002, TST-ELG-007 | DQ-A, DQ-D |
| FUN-003 | When no eligible content answers a question, the response is the same as when no such content exists; it never indicates that restricted content exists | The existence of a restricted section can itself be sensitive | MUST | OBJ-2 · CISO | TST-ELG-008 | DQ-F |
| FUN-004 | A document's INTERNAL sections remain answerable for all staff when other sections of the same document are CONFIDENTIAL or RESTRICTED | Section granularity preserves the value of mixed documents | MUST | OBJ-1 · Head of Engineering Knowledge | TST-ELG-004 | DQ-B |

## Security

| ID | Requirement | Rationale | Priority | Source | Verified by | Related decisions |
|---|---|---|---|---|---|---|
| SEC-001 | **INVARIANT.** An employee never receives content from a section whose classification and scope they are not eligible for — not in retrieval results, generated answers, citations, source metadata or error messages | The central disclosure risk | MUST | OBJ-2 · CISO · DPO | TST-ELG-003, TST-ELG-005, TST-ELG-006, TST-SEN-001 | DQ-A, DQ-D |
| SEC-002 | **INVARIANT.** The requester's identity is taken only from a verified token issued by the workforce identity provider; a request without a valid token receives no retrieval and no answer | No anonymous or asserted identity | MUST | CISO | TST-SEC-001 | DQ-E |
| SEC-003 | **INVARIANT.** Entitlements are taken only from the authoritative entitlement sources at request time. Entitlement values in the request, the question text, token claims beyond identity, or document content are never trusted | Prevents asserted, stale or injected entitlements | MUST | OBJ-5 · CISO | TST-SEC-002, TST-CHG-001 | DQ-E |
| SEC-004 | **INVARIANT.** Retrieval eligibility is decided **before** any content is retrieved. Ineligible content never enters retrieval results or model context; removing it afterwards does not satisfy this requirement | Retrieved content has already crossed the boundary | MUST | OBJ-2 · CISO | TST-ELG-003, TST-SEN-001 | DQ-D |
| SEC-005 | **INVARIANT.** Instructions in a question or inside document content cannot widen retrieval eligibility; eligibility never depends on a model following instructions | Models can be persuaded | MUST | CISO | TST-SEC-003 | DQ-D |
| SEC-006 | **INVARIANT.** Authentication, employment, department, job title and seniority never by themselves grant CONFIDENTIAL or RESTRICTED content; only an explicit domain membership or case assignment does | Need-to-know is not seniority (RSK-05) | MUST | OBJ-2 · HR Director · Head of Safety Investigations | TST-ELG-006, TST-ELG-007 | DQ-A |
| SEC-007 | **INVARIANT.** If the requester's entitlements cannot be resolved, or a section's classification or scope is missing, unknown or malformed, that content is not retrievable and the event is recorded (fails closed) | An unknown must never mean "everything" | MUST | CISO | TST-SEC-005, TST-SEC-006, TST-DATA-001, TST-DATA-002 | DQ-B, DQ-E |
| SEC-008 | Before generation, each retrieved chunk's classification and scope are re-checked against the authoritative classification record and the requester's entitlements; any mismatch withholds the whole answer and records a security event | Detects label corruption, tampering and stale labels before content reaches the model | MUST | CISO · Records Manager | TST-SEC-007, TST-SEN-002 | DQ-F |
| SEC-009 | No route available to employees or their client applications reaches indexed content without passing the eligibility decision | A boundary with a side door is not a boundary | MUST | CISO | TST-SEC-004 | DQ-D |
| SEC-010 | A revoked domain membership or case assignment stops granting eligibility for requests made after the entitlement source records the revocation | People leave bids, cases and teams constantly (RSK-03) | MUST | OBJ-5 · Commercial Director · HR Director | TST-CHG-001, TST-SEN-003 | DQ-E |
| SEC-011 | An upward reclassification recorded in the classification source stops the content being used in answers for newly ineligible employees from their next request, even before the index is updated | The index is a copy; the record is the authority (RSK-04) | MUST | Records Manager · CISO | TST-CHG-002 | DQ-F |
| SEC-012 | Audit and operational records capture who asked, the eligibility decision, the labels, scope identifiers and outcomes of retrieved and withheld items — and never document content, excerpts, answer text or question text | Explainability without creating a new copy of sensitive content (RSK-06) | MUST | OBJ-4 · DPO · Employee representatives | TST-OBS-001 | DQ-G |
| SEC-013 | Each component holds only the permissions its function needs; content in the restricted tier is readable only through the path that serves eligible RESTRICTED requests | Limits the blast radius of a defect or compromise | MUST | CISO | TST-SEC-004, review | DQ-D |

## Data

| ID | Requirement | Rationale | Priority | Source | Verified by | Related decisions |
|---|---|---|---|---|---|---|
| DATA-001 | Every document and every marked section has exactly one label from the approved taxonomy (INTERNAL, CONFIDENTIAL, RESTRICTED). CONFIDENTIAL carries exactly one access domain; RESTRICTED carries exactly one case; INTERNAL carries none | Eligibility can only be as precise as the labels it evaluates | MUST | Records Manager | TST-DATA-002 | DQ-B |
| DATA-002 | Classification and scope are taken only from the owner-assigned classification record in the records system — never inferred from document text by the assistant | The records system stays the single classification authority (CON-002) | MUST | Records Manager · CON-002 | TST-DATA-003 | DQ-B |
| DATA-003 | Every chunk carries the effective classification and scope of the section it came from; a chunk never spans sections with different labels or scopes; the effective label is never less restrictive than the document's own label | Mixed documents must not leak their most sensitive section (RSK-01) | MUST | CISO · Records Manager | TST-ELG-004, TST-DATA-005, TST-SEN-002 | DQ-B |
| DATA-004 | Content marked as special-category personal data (for example medical information) is never indexed, embedded, cached or sent to a model | No assistant use case needs it; the safest retrieval boundary is data that was never indexed | MUST | DPO · OBJ-3 | TST-DATA-004 | DQ-C |
| DATA-005 | Documents or sections that fail classification validation are excluded from the index and reported to the records manager | Invalid labels must not default to anything retrievable | MUST | Records Manager · CISO | TST-DATA-001, TST-DATA-002 | DQ-B |
| DATA-006 | Anything derived from content — index entries, embeddings, cached answers, evaluation sets, logs — is classified at least as high as its source | Derived data carries its source's sensitivity | MUST | DPO · CISO | TST-DATA-006, TST-OBS-001 | DQ-C, DQ-D |
| DATA-007 | For every indexed chunk the system can state its source document, section, effective classification, scope and the classification-record version it was indexed from | Needed to verify, investigate and re-index | MUST | Records Manager | TST-DATA-005 | DQ-B |

## Non-functional

| ID | Requirement | Rationale | Priority | Source | Verified by | Related decisions |
|---|---|---|---|---|---|---|
| NFR-001 | During the pilot, the eligibility decision and constraint construction add no more than about half a second to the median answer time (**ASSUMPTION** target; ASM-007) | Per-request authorization must not make the assistant unusable | SHOULD | Product owner | TST-SCALE-001 | DQ-E |
| NFR-002 | Eligibility remains correct for an employee holding up to about 40 domain memberships and case assignments (ASM-002); if a decision cannot be represented completely, the request fails closed rather than truncating | Large entitlement sets must never be silently cut | MUST | CISO · Platform team | TST-SCALE-001 | DQ-D, DQ-E |
| NFR-003 | If current authorization cannot be established from the authoritative sources (for example the entitlement registry or HR system is unavailable), no retrieval occurs — not even INTERNAL. The user receives a safe, uniform failure that reveals nothing about restricted content, and a content-free audit event is recorded. There is no alternate authorization mode | No authoritative current grants means no retrieval; a degraded mode would be a second, weaker authorization path | MUST | CISO | TST-SEC-005 | DQ-E |
| NFR-004 | The cost per 1,000 questions of the pilot design is estimated and stated before build | The design must be affordable; detailed cost optimisation is Episode 05 | SHOULD | COO | review | DQ-D |
| NFR-005 | The assistant is available during pilot business hours; out-of-hours support is not required for the pilot | Pilot scope | COULD | Platform team | review | — |

## Operational

| ID | Requirement | Rationale | Priority | Source | Verified by | Related decisions |
|---|---|---|---|---|---|---|
| OPS-001 | Quarantined content and verification mismatches are visible to the records manager and the security team within one business day | Labels get fixed only if someone sees the failures | SHOULD | Records Manager · CISO | TST-OBS-002 | DQ-G |
| OPS-002 | The eligibility decision for any past request can be reconstructed from its audit record and the versions of the entitlement and classification records it used | "Why could this person see that?" must have an answer | MUST | OBJ-4 · DPO | TST-OBS-002 | DQ-G |
| OPS-003 | The validation suite runs repeatably and unattended from a fresh copy of the engagement | Evidence must be reproducible by a learner | MUST | Season standard | TST-OPS-001 | — |

## Compliance (Kestrelmoor policy obligations, not legal advice)

| ID | Requirement | Rationale | Priority | Source | Verified by | Related decisions |
|---|---|---|---|---|---|---|
| CMP-001 | Processing of employee personal data through the assistant is limited to what the approved use cases need, as set by Kestrelmoor's Data Protection Officer | Data minimisation is Kestrelmoor policy | MUST | DPO | TST-DATA-004, review | DQ-C |
| CMP-002 | Audit records are retained for the period set by Kestrelmoor's records policy and then deleted (**ASSUMPTION**: 12 months) | Proportionate monitoring of staff | SHOULD | DPO · Employee representatives | review | DQ-G |
