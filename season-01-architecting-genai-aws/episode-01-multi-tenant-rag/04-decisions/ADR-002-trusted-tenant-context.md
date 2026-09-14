<!-- template: tla-adr/1 -->
# ADR-002 — Tenant identity source: tenant context from a verified claim, validated against the tenant registry

**Status:** proposed — awaiting architecture approval · **Date:** 2026-09-14
**Answers:** decision question DQ-B · **Options analysis:** [section 3](ARCHITECTURE_OPTIONS_ANALYSIS.md#3-tenant-context-source--adr-002)

## Context

Users sign in through Veltamere's existing identity provider, which remains authoritative for identity and tenant
membership (CON-004). It issues signed tokens carrying the user's identifier and tenant membership; a session has exactly
one active tenant, and users who belong to several tenants switch explicitly (ASM-004). **One legacy endpoint already
trusts a tenant identifier supplied in the request** — the pattern this decision must make impossible for the assistant.

A token claim is not trustworthy merely because it exists. It is trustworthy only when the token is proven genuine,
current and intended for this API, and when the claim is issued from membership that the user cannot edit.

## Requirements driving this decision

- **SEC-003** (invariant) — tenant context only from verified identity; caller-supplied tenant identifiers never trusted.
- **SEC-002** — every question attributed to an authenticated identity; unauthenticated requests get nothing.
- **SEC-008** (invariant) — missing, malformed or unresolvable context → no retrieval, event recorded.
- **BUS-001** — a disabled tenant is never served.
- **NFR-002**, **BUS-002** — onboarding without code or per-tenant rules.
- Constraints and assumptions: CON-004, ASM-004, ASM-005.

## Options considered

| Option | How tenant context is obtained | Verdict |
|---|---|---|
| A — Caller-supplied tenant ID | Path, query, body, header or question text names the tenant | Fails SEC-003 |
| B — Verified token claim only | Claim from a verified token | Cannot see a tenant disabled after issue; otherwise sound |
| C — Server-side membership lookup | Verified user identifier looked up in a platform-held membership copy | Sound, but duplicates membership the identity provider owns (CON-004) — a second copy that can drift |
| **D — Verified claim validated against the tenant registry** | B, plus a server-side check that the tenant exists and has the assistant enabled | Chosen |

## Trade-offs

Claims alone are fast and keep the identity provider authoritative, but a claim is a snapshot taken when the token was
issued. A server-side lookup is current, but copying membership into the platform creates a second authority. D keeps
**membership** authority with the identity provider and **tenant status** authority with Veltamere's tenant registry — the
two things each system genuinely owns — at the cost of one registry read per request.

## Decision

1. **The API edge verifies the token** before any service code runs (CTL-003).
2. **The Tenant Context Resolver** — a shared module inside the query and ingestion services — is **the only component
   trusted to establish tenant context**. It reads claims **only** from the edge's verified claim set, and builds an
   immutable tenant context `{tenant_id, user_id}` (CTL-004).
3. The resolver requires **exactly one** tenant membership value. None, several or a malformed value → deny (fail closed).
4. The resolver validates the tenant against the **tenant registry**: it must exist and have the assistant **ENABLED**.
   Unknown or disabled → deny. Registry unreachable → deny with a retryable error; never "allow and hope" (CTL-005).
5. **Caller-supplied tenant identifiers are never read.** The request body accepts only the documented fields; any other
   field — including anything resembling a tenant identifier — is refused with a client error and recorded. Path, query
   and header values are never consulted for tenant (CTL-004).
6. **Membership must be issued from administrator-controlled data.** A tenant value that users can edit through
   self-service profile updates is not an acceptable source (CTL-006).
7. **Switching tenants** (ASM-004) means obtaining a new token for the other tenant from the identity provider. The
   assistant never offers a tenant parameter.

### What must be verified

| Check | Where | Why | On failure |
|---|---|---|---|
| Signature, using the issuer's published signing keys | API edge | Proves the token was issued by the trusted identity provider and not altered | Refused before any service runs |
| Issuer equals the configured identity provider | API edge | A token from another issuer proves nothing | Refused |
| Audience or client identifier equals the assistant's registered client | API edge | A token issued for another application must not be replayed here | Refused |
| Expiry, not-before and issued-at are valid | API edge | Limits replay of old or future-dated tokens | Refused |
| Token type is an access token for this API (required scope, token-use claim) | API edge (scope) · resolver (token use) | Identity tokens are meant for the client, not for API authorisation | Denied |
| Subject (user identifier) present | Resolver | Every question must be attributable (SEC-002, OPS-001) | Denied |
| Exactly one well-formed tenant membership value | Resolver | Ambiguous context must never widen scope (ASM-004) | Denied — `TENANT_CLAIM_MISSING` / `TENANT_CLAIM_AMBIGUOUS` |
| Tenant exists and assistant is ENABLED in the registry | Resolver | Unknown tenants and disabled tenants are never served (BUS-001) | Denied — `TENANT_UNKNOWN` / `TENANT_DISABLED`; unreachable → `REGISTRY_UNAVAILABLE` |
| Membership semantics: the claim is issued from administrator-controlled membership and is not user-writable | Identity provider configuration (review) | A verified signature over a user-chosen value is still a user-chosen value | Configuration defect — blocks go-live |

## Why not the other options

- **Why not A?** It is the legacy export endpoint's pattern. Any authenticated user could read any tenant by naming it.
- **Why not B alone?** A tenant disabled after a token was issued would still be served until the token expired, which
  violates BUS-001's "never retrieved" and gives Veltamere no immediate stop control during an incident.
- **Why not C?** It moves membership authority into a platform-held copy that must be synchronised with the identity
  provider. Drift between the two becomes a new way to authorise the wrong tenant, and it contradicts CON-004.

## Consequences

**Positive**
- The tenant cannot be chosen by the caller in any field; the trust transition from untrusted request to trusted context
  happens in one named component.
- Disabling a tenant takes effect on the next request (registry check), without revoking tokens.
- Onboarding is data: identity-provider membership plus a registry entry (NFR-002).

**Negative / accepted trade-offs**
- One registry read per request (latency; NFR-001 review).
- The registry becomes security-critical data: only the onboarding workflow may write it.
- Removing a user from a tenant takes effect when the user's token expires (RR-11).
- The architecture inherits the identity provider's correctness: a user wrongly placed in a tenant is authorised for that
  tenant (ASM-005, RR-01).

## Residual risks

RR-01 identity provider compromise or incorrect membership · RR-11 membership removal effective at token expiry.

## Controls introduced

| ID | Control | Enforcement point |
|---|---|---|
| CTL-003 | **Edge token verification.** Every assistant route requires a token whose signature, issuer, audience or client, expiry, not-before, issued-at and scope are verified; failures never reach service code | API edge authoriser on every route |
| CTL-004 | **Tenant context only from verified claims.** The resolver builds tenant context from the edge's verified claims (subject + exactly one tenant membership value); request bodies accept only documented fields; path, query, header and question text are never read for tenant | Tenant Context Resolver (query and ingestion services) |
| CTL-005 | **Tenant registry validation.** The claimed tenant must exist and have the assistant ENABLED; unknown, disabled or unreachable → deny, recorded | Tenant Context Resolver → tenant registry |
| CTL-006 | **Membership claim integrity.** Tenant membership in tokens is issued from administrator-controlled membership, is not writable through user self-service, and yields exactly one active tenant per session | Identity provider configuration |

## Validation implications

- TST-SEC-005 places Tenant B's identifier in every caller-controlled field while authenticated as Tenant A.
- TST-SEC-007 covers missing, expired, wrongly signed, wrong-audience and identity-type tokens.
- TST-SEC-013 covers missing claim, several tenant values, unknown tenant and an unreachable registry.
- TST-DATA-016 disables a tenant with valid tokens still in circulation.
- TST-OPS-017 onboards Tenant C with no code change.

## Platform evidence (checked after the decision)

- The edge authoriser in the implementation environment verifies signature, issuer, audience or client identifier,
  expiry, not-before, issued-at and scopes, and passes verified claims to the integration (PC-17). It cannot tell access
  tokens from identity tokens by itself, so routes require a scope (PC-18) — hence the token-type row above.
- In the learner identity-provider stand-in, application clients can write user attributes by default, and the default
  access-token scope lets users modify their own profile (PC-19, PC-20). **A tenant stored as a user profile attribute
  would therefore be user-writable unless deliberately locked down.** The learner implementation expresses membership as
  administrator-managed groups instead (TS-01), which satisfies CTL-006.

## Related

- Requirements: SEC-002, SEC-003, SEC-008, BUS-001, BUS-002, NFR-002
- Decisions: ADR-003, ADR-004
- Tests: TST-SEC-005, TST-SEC-007, TST-SEC-013, TST-DATA-016, TST-OPS-017
