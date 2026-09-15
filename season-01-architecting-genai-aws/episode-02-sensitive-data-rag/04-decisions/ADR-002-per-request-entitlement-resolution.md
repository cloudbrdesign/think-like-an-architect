<!-- template: tla-adr/1 -->
# ADR-002 — Entitlements resolved per request by a policy decision point

**Status:** accepted (2026-09-15) · **Date:** 2026-09-15 · **Answers:** DQ-E · **Options:** [section 5](ARCHITECTURE_OPTIONS_ANALYSIS.md#5-entitlement-source-and-decision-timing--adr-002)

## Context

**The authorities.** Identity comes from the workforce identity provider. Employment status comes from the HR system.
Domain memberships and case assignments come from the entitlement registry (CON-003).

**Why token claims can't serve.** They can be about an hour stale (ASM-008), and people move between bids and cases
constantly.

**Requirements:** SEC-002, SEC-003, SEC-007, SEC-010, NFR-001, NFR-002, NFR-003.

## Decision

**Edge:** accepts only a verified token and passes only the verified employee identifier.

**Policy decision point** — for every request, before retrieval, it:
- resolves employment status, memberships and assignments from the authoritative sources, recording their versions;
- computes the eligibility decision under ADR-001.

**Never trusted:** token group claims, request fields, headers, query parameters and the question text.

**On failure:** if current authorization cannot be established from the authoritative sources — resolution fails, a
source is unavailable, or the person has no record — **no retrieval occurs, for any label.** The user receives the safe
uniform failure, and a content-free audit event names the failing source. There is no degraded or alternate
authorization mode.

## Alternatives considered

- **Token claims:** stale; size-limited; fails SEC-010.
- **Periodic snapshot:** revocation waits for refresh. Kept as a measured optimisation, not a default.

## Rationale

**Timing:** revocation takes effect from the next request after the registry records it (SEC-010).
**Auditability:** every decision is traceable to source versions (OPS-002).

## Consequences

- **Positive:**
  - no stale grants inside the assistant;
  - one decision component;
  - asserted entitlements are impossible by construction.
- **Negative / accepted trade-offs:**
  - a lookup per request adds latency (NFR-001);
  - the entitlement source becomes a runtime dependency, and its outage stops all answers (NFR-003, RR-12).

## Risks

**Registry lag** (ASM-005, RR-02). **Very large entitlement sets** (RR-10).

## Controls introduced

| ID | Control | Enforcement point |
|---|---|---|
| CTL-002 | Only a verified token establishes identity; anything else is refused before any downstream call | Edge |
| CTL-003 | Status, memberships and case assignments resolved per request from the HR system and entitlement registry, with versions; claims, request values and text ignored | Policy decision point |
| CTL-004 | No authoritative current grants → no retrieval: an unavailable source, failed resolution or missing record stops the request before any search call; safe uniform failure; content-free audit event | Policy decision point |

## Related
- **Requirements:** SEC-002, SEC-003, SEC-007, SEC-010, NFR-001, NFR-002, NFR-003.
- **Tests:** TST-SEC-001, TST-SEC-002, TST-SEC-005, TST-SEC-006, TST-CHG-001, TST-SCALE-001, TST-SEN-003.
- **Validation implication:** TST-SEN-003 builds a variant that reads token claims instead. The revocation test must fail
  there.
