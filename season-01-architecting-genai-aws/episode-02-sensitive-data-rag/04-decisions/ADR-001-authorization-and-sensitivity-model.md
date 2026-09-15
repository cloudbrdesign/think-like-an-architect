<!-- template: tla-adr/1 -->
# ADR-001 — Authorization and sensitivity model: labels with scopes, and explicit entitlements

**Status:** accepted (2026-09-15) · **Date:** 2026-09-15 · **Answers:** DQ-A · **Options:** [section 1](ARCHITECTURE_OPTIONS_ANALYSIS.md#1-authorization-and-sensitivity-model--adr-001)

## Context

**The situation.** Kestrelmoor is one organisation. Every user is an authenticated employee, and every document belongs
to the company.

**The problem.** Access to the information inside documents follows compartments and need-to-know, not seniority:
- bid pricing is for the bid team;
- witness statements are for assigned investigators;
- HR case files are for the case owner.

**Requirements:** SEC-001, SEC-006, FUN-002, BUS-001, BUS-002, BUS-003.

## Decision

**Sensitivity:** each section carries one label from INTERNAL, CONFIDENTIAL, RESTRICTED, and a scope:
- CONFIDENTIAL → exactly one access domain;
- RESTRICTED → exactly one case;
- INTERNAL → no scope.

**Authorization:** three attributes of the requester, all from authoritative sources — employment status, domain
memberships, case assignments.

**Eligibility:**
- **Active employee:** eligible for INTERNAL.
- **Domain member:** eligible for CONFIDENTIAL in that domain.
- **Case assignee:** eligible for RESTRICTED in that case.
- **Never inputs:** department, title, grade and seniority are not inputs to the rule.

## Alternatives considered

- **Hierarchical clearance:** fails SEC-006.
- **Role or department groups:** too coarse; fails SEC-006.
- **Per-document access lists:** not section-level (fails FUN-004); drift and size.

## Rationale

**It matches how Kestrelmoor governs its information:** owners grant compartments and assign cases.
- **Small decisions:** a person's eligibility is a label set plus a few scope IDs, not a list of documents.
- **Owners' control:** they change access in the registry without touching the assistant (BUS-002).

## Consequences

- **Positive:**
  - need-to-know is explicit;
  - seniority cannot quietly widen access;
  - adding a domain or case type is configuration (BUS-003).
- **Negative / accepted trade-offs:**
  - owners must grant access explicitly, so some senior staff will see less than they expect (RR-07);
  - label correctness remains the owners' responsibility (RR-01).

## Risks

**Pressure for implicit overrides** (RR-07). **Grants that are wrong at the source** (RR-02).

## Controls introduced

| ID | Control | Enforcement point |
|---|---|---|
| CTL-001 | One eligibility rule: active status, plus label and scope against memberships and assignments. Department, title, grade, token claims, request fields and text are not inputs | Policy decision point, before every retrieval |

## Related
- **Requirements:** SEC-001, SEC-006, FUN-002, BUS-001, BUS-002, BUS-003.
- **Tests:** TST-ELG-001, TST-ELG-002, TST-ELG-006, TST-ELG-007.
- **Validation implication:** the synthetic corpus includes a senior persona with no case assignments (P-07), and
  assignees who are negative for each other's cases (P-05, P-06).
