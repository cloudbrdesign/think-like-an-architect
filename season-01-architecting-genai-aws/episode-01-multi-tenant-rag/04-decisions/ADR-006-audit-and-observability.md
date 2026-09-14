<!-- template: tla-adr/1 -->
# ADR-006 — Audit and observability: one content-free security audit record per request

**Status:** proposed — awaiting architecture approval · **Date:** 2026-09-14
**Answers:** decision question DQ-F · **Options analysis:** [section 7](ARCHITECTURE_OPTIONS_ANALYSIS.md#7-audit-and-observability--adr-006)

## Context

Today, searches are not logged at all. Veltamere must be able to investigate a suspected exposure, meet notification
duties and give customers annual evidence that isolation is tested. The obvious shortcut — logging everything — would
copy confidential documents and answers into logs, creating a second leakage path.

## Requirements driving this decision

- **OPS-001** — per question: authenticated user, tenant context, decision, identifiers of retrieved documents, outcome.
- **OPS-002** — access-decision records contain no full document content or full answers by default.
- **CMP-001** — segregation demonstrable with test results and access records.
- **SEC-011** — records derived from tenant data are protected.
- **SEC-009**, **RSK-08** — bypass and privileged access must be detectable.

## Options considered

| Option | What is recorded | Verdict |
|---|---|---|
| A — Platform API activity records only | The provider's record of API calls | Records the service identity, not the end user or tenant |
| B — Full request and response logging | Questions, retrieved text, answers | Fails OPS-002 |
| **C — Content-free security audit record per request, written by the authorising component** | Who, which tenant, what was decided and why, which constraint, which documents, what outcome | Chosen |
| D — Retrieval-layer access logs only | What the store returned | Misses refusals and reasons |

## Trade-offs

Content-free records answer "who, which tenant, what decision, which documents" but cannot show **what the answer said**.
Investigating answer content requires reproducing the question against the recorded documents. That is accepted: the
alternative makes every log reader a potential cross-tenant reader.

## Decision

1. **The authorising components write the record.** The retrieval gateway (query path) and the ingestion service
   (upload, open, delete) write exactly one security audit record per request, including every denial and every
   failure (CTL-019).
2. **Security audit data is separate from application data.** Audit records go to a dedicated, access-restricted store,
   read only by the security role. Operational logs are separate and never contain request or response bodies, question
   text, chunk text or answers (CTL-020).
3. **Retention** covers at least one annual evidence cycle and the investigation period for a notification
   (**ASSUMPTION** — the exact period is agreed with Legal before production).
4. **Records are internal to Veltamere.** A customer's evidence request is answered with an extract filtered to that
   customer's tenant.
5. **Bypass detection.** The cloud provider's activity records for retrieval and indexing operations are monitored, and
   any call by a principal other than the gateway, the ingestion service or the indexing service raises an alert
   (CTL-021).
6. **The API edge** records rejected tokens (time, route, reason) without recording token contents.

### Security audit record fields

| Field | Purpose | Contains document content or answer text? |
|---|---|---|
| `event_id` (correlation identifier) | Join edge, service and platform records | No |
| `timestamp`, `route`, `action` (`ask`, `upload`, `open`, `delete`) | What was attempted, when | No |
| `user_id` (identity-provider subject) | **Who** made the request | No (pseudonymous identifier) |
| `token_issuer`, `client_id` | Which trusted issuer and application | No |
| `tenant_context` (or `NONE`) | **Which tenant** the verified identity mapped to | No |
| `decision` (`ALLOW`/`DENY`) and `reason_code` | **Whether** authorisation allowed or denied, and why | No |
| `failed_control` (for example `CTL-005`) | **Which control** failed or fired | No |
| `constraint_applied` (attribute, value, structure identifier) or `NONE` | **Which retrieval boundary** was applied | No |
| `retrieved` — list of document identifiers with their owner attribute, before verification | What crossed the retrieval boundary; the primary observation point for isolation tests | No |
| `verification_outcome` (`PASSED`, `DISCARDED:n`, `OWNERSHIP_MISMATCH`) | Whether defence in depth fired | No |
| `cited_document_ids` | What the user was shown as sources | No |
| `outcome`, `status_code`, `latency_ms` | Result | No |
| `question_length` (characters) | Diagnostics without content | No |

**Reason codes:** `TENANT_CLAIM_MISSING` · `TENANT_CLAIM_AMBIGUOUS` · `TENANT_UNKNOWN` · `TENANT_DISABLED` ·
`REGISTRY_UNAVAILABLE` · `REQUEST_FIELD_REJECTED` · `CONSTRAINT_UNBUILDABLE` · `OWNERSHIP_MISMATCH` ·
`ATTRIBUTION_INCONSISTENT` · `NOT_FOUND_FOR_TENANT` · `ALLOWED`.

### The investigation questions this answers

| Question | Answered by |
|---|---|
| Who made the request? | `user_id`, `token_issuer`, `client_id` |
| Which tenant did the trusted identity map to? | `tenant_context` |
| Was authorisation allowed or denied? | `decision`, `reason_code` |
| Which retrieval boundary was applied? | `constraint_applied` |
| What control failed? | `failed_control`, `verification_outcome` |
| Which documents could have informed the answer? | `retrieved`, `cited_document_ids` |
| Did anything else retrieve data? | Bypass detection alert (CTL-021) |

## Why not the other options

- **Why not platform activity records alone (A)?** They show that the gateway called retrieval, not which user or tenant
  it acted for, nor why a request was refused.
- **Why not full logging (B)?** Every reader of the logs would become a reader of every tenant's documents (RSK-11).
- **Why not retrieval-layer logs only (D)?** Denials never reach the retrieval layer, so fail-closed behaviour and forged
  tenant attempts would be invisible.

## Consequences

**Positive**
- An investigator can reconstruct any request's decision and retrieved documents without seeing their content.
- Isolation tests read the retrieval layer's outcome from the record, independently of what the model wrote.

**Negative / accepted trade-offs**
- Answer text cannot be recovered from records; investigations re-run questions against the recorded documents.
- The audit store itself is sensitive metadata (document identifiers, who asked) and needs restricted access.
- Monitoring retrieval calls as platform data events adds cost (PC-22).

## Residual risks

RR-02 privileged access to audit and content stores · RR-08 content logging enabled later by mistake.

## Controls introduced

| ID | Control | Enforcement point |
|---|---|---|
| CTL-019 | **Security audit record per request** with the fields above, including denials and failures, written by the component that decided | Retrieval gateway; ingestion service; dedicated audit store |
| CTL-020 | **Content-free operational logging.** Operational logs never record request or response bodies, question text, chunk text or answers; audit and operational data are stored separately with separate access | Service logging configuration; log access policies |
| CTL-021 | **Bypass detection.** Retrieval and indexing operations by any principal other than the gateway, ingestion or indexing service identities raise an alert | Platform activity records and alerting |

## Validation implications

- TST-OPS-015 inspects records from TST-ISO-003 and TST-SEC-013: an investigator can answer the questions above, and no
  document marker phrase appears in any record or log.
- TST-SEN-011 reads the `retrieved` field to observe the leak at the retrieval layer.
- TST-SEC-009 checks that a bypass attempt produces an alert where CTL-021 is implemented.

## Platform evidence (checked after the decision)

- Retrieval operations are recorded by the platform only as **data events**, which must be enabled and carry
  additional charges (PC-22). The learner implementation may substitute a permission check for the live alert
  (TS-06); CTL-021 remains part of the production architecture.
- Model invocation logging, when enabled, records full request and response bodies (PC-21) — addressed in ADR-007
  (CTL-024).

## Related

- Requirements: OPS-001, OPS-002, CMP-001, SEC-011, SEC-009
- Decisions: ADR-003, ADR-005, ADR-007
- Tests: TST-OPS-015, TST-SEN-011, TST-SEC-009
