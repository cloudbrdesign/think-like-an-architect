<!-- template: tla-adr/1 -->
# ADR-004 — Sensitivity-tiered retrieval with a mandatory eligibility constraint

**Status:** accepted (2026-09-15) · **Date:** 2026-09-15 · **Answers:** DQ-D · **Options:** [section 4](ARCHITECTURE_OPTIONS_ANALYSIS.md#4-retrieval-eligibility-enforcement-and-index-topology--adr-004)

## Context

**The central question of this episode.** What technical boundary guarantees that sections a legitimate employee is not
eligible for are never retrieval candidates?

**How the answer must behave:**
- it must not depend on the model;
- it must fail closed;
- it must scale to about 150 domains and 400 cases with a six-person team;
- a single defect must not expose the most harmful content to everyone.

**Requirements:** SEC-001, SEC-004, SEC-005, SEC-009, SEC-013, NFR-002, NFR-004, FUN-001, FUN-002.

## Decision

**Two search tiers:**
- **Shared tier:** INTERNAL and CONFIDENTIAL chunks. Every query carries the gateway-built constraint
  `label = INTERNAL OR (label = CONFIDENTIAL AND domain ∈ requester memberships)`, evaluated during search.
- **Restricted tier:** RESTRICTED chunks. Queried **only** when the decision contains case assignments, with the
  constraint `label = RESTRICTED AND case ∈ requester assignments`, evaluated during search.

**Gateway rules:**
- **Source:** it builds constraints only from the policy decision point's decision. Nothing from the question or content
  can alter them.
- **Completeness:** if it cannot build a complete constraint (including when a decision is too large to represent), it
  makes no retrieval call and refuses.

**Access:** only the gateway's identity may query either tier.

## The tier is not the authorization boundary (2026-09-15)

- **Layer 1 — blast-radius reduction:** tiers limit what one retrieval structure contains. They are defence in depth.
- **Layer 2 — authorization enforcement:** the mandatory constraint, built from the authoritative current decision
  (ADR-002), decides what the requester may retrieve inside whichever tier is queried.
- **Consequence:** a requester routed to the restricted tier because they hold one case assignment retrieves nothing
  from any other case; a shared-tier query retrieves no CONFIDENTIAL domain the requester is not a member of. Tier
  selection is never used as, or described as, an authorization decision (TST-ELG-009).

## Alternatives considered

| Alternative | Why not |
|---|---|
| Per-domain and per-case indexes | About 550 structures; operationally infeasible |
| **One shared index with the full constraint** | **The credible runner-up:** simpler, but one defect exposes RESTRICTED content to everyone |
| Post-retrieval eligibility | Fails SEC-004; retained only as verification (ADR-005) |
| Prompt instructions | Fails SEC-005 |
| Answer redaction | Fails SEC-004 |

## Rationale

**Separate by sensitivity where blast radius justifies it; constrain inside the search where scale requires it.**

**Same question, different answer:**
- **Episode 01** chose one shared structure, because every tenant's content had equal sensitivity.
- **Here** the harm differs sharply by tier, and so does the topology.

## Consequences

- **Positive:**
  - the shared constraint cannot expose witness statements or HR cases, because they are not in the shared tier;
  - the restricted tier has a separate, narrower access path;
  - cross-domain questions work natively.
- **Negative / accepted trade-offs:**
  - two retrieval calls, with merged ranking, for case-assigned users;
  - ingestion routing becomes security-relevant;
  - two structures to operate and pay for (NFR-004);
  - large entitlement sets can hit search-constraint limits and fail closed (RR-10).

## Risks

**A constraint mis-evaluated inside a search component the architecture does not own** (RR-11, detected by ADR-005).
**A routing defect** (tested). **Constraint size limits** (to be verified before build).

## Controls introduced

| ID | Control | Enforcement point |
|---|---|---|
| CTL-005 | Only the retrieval gateway's identity may query the shared or restricted tier; no other route reaches indexed content | Invocation permissions on both tiers |
| CTL-011 | Shared-tier eligibility constraint built from the decision and evaluated during search | Gateway → shared tier |
| CTL-012 | Restricted tier queried only for requesters with case assignments, with a case constraint evaluated during search | Gateway → restricted tier |
| CTL-013 | Complete constraint or no retrieval: nothing from question or content changes it; incomplete or too-large decisions refuse | Gateway |

## Related
- **Requirements:** SEC-001, SEC-004, SEC-005, SEC-009, SEC-013, NFR-002, NFR-004, FUN-001, FUN-002.
- **Tests:** TST-ELG-001 … TST-ELG-007, TST-SEC-003, TST-SEC-004, TST-SCALE-001, TST-SEN-001.
- **Validation implication:** TST-SEN-001 removes the eligibility clauses in a separate deployment. The negative
  eligibility tests must fail there.
