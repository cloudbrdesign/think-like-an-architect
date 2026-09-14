<!-- template: tla-adr/1 -->
# ADR-001 — Tenant isolation model: one shared retrieval structure with an enforced tenant partition

**Status:** proposed — awaiting architecture approval · **Date:** 2026-09-14
**Answers:** decision question DQ-A · **Options analysis:** [section 2](ARCHITECTURE_OPTIONS_ANALYSIS.md#2-tenant-isolation-model--adr-001)

## Context

Veltamere serves about 120 competing facilities-management companies from one shared platform, growing towards 400
(ASM-001). Each tenant's documents must never inform another tenant's answers, citations or metadata. The platform team
is five engineers and one SRE (CON-003), customer contracts require **logical** segregation of each customer's data, and
pricing assumes shared infrastructure. The question is what the unit of isolation for retrieval data should be.

## Requirements driving this decision

- **SEC-001** (invariant) — no Tenant B information in any Tenant A output channel.
- **SEC-004** (invariant) — authorisation before retrieval; no other tenant's content in retrieval results.
- **DATA-002** — derived retrieval data carries or inherits the owning tenant.
- **NFR-002** — adding a tenant needs no code change and no hand-written per-tenant rule.
- **NFR-004** — cost grows mainly with usage, not with tenant count, unless a decision justifies otherwise.
- **CMP-001** — logical segregation can be demonstrated with tests and records.
- **CMP-002**, **SEC-011** — tenant data and derived data protected and kept in the contracted region.
- **BUS-002**, **NFR-003** — repeatable onboarding; the assistant is additive.
- Constraints and assumptions: CON-002, CON-003, CON-006, CON-008, ASM-001, ASM-002, ASM-007.

## Options considered

| Option | Isolation boundary | Blast radius of one defect | Onboarding | Operations | Cost structure |
|---|---|---|---|---|---|
| A — Dedicated retrieval structure per tenant (and A′, per-tenant environment) | Resource separation + routing | One tenant (misroute) | Per-tenant provisioning | N structures | Fixed cost × tenants |
| **B — Shared structure, enforced tenant partition** | Tenant constraint evaluated inside the search, on an owning-tenant attribute set at ingestion | All tenants in the structure, if the constraint were missing | Registry entry | One structure | Usage-driven |
| C — Grouped cells / tiered hybrid | Routing to a cell + tenant constraint | Tenants in one cell | Registry entry + cell assignment | K structures | Fixed cost × cells + usage |
| D — Shared structure, per-user access lists | Store evaluates lists against a caller-supplied identity | All documents reachable by the supplied identity | Per-user lists on every document | Medium, high churn | Usage + re-indexing |

## Trade-offs

**Stronger physical separation** (A) usually reduces cross-tenant blast radius, but it increases resource count,
operational work, onboarding complexity, cost and lifecycle management — and its routing is still a software decision.
**Shared logical isolation** (B) improves operational efficiency, onboarding and resource utilisation, but it makes the
correctness of identity, authorisation, attribution, retrieval filtering and bypass prevention **much more critical**,
because one missing constraint would expose every tenant at once. Neither is universally better; the requirements decide.

## Decision

**Option B.** All enabled tenants share one retrieval structure. Every chunk carries exactly one owning-tenant attribute,
assigned at ingestion by the trusted ingestion service (ADR-004). Every retrieval is constrained to exactly one tenant —
the tenant in the verified tenant context (ADR-002) — by a constraint that the authoritative gateway builds (ADR-003) and
the retrieval structure evaluates during the search (ADR-005).

**The decision is valid only together with these conditions.** If any is removed, Option B no longer passes the isolation
gate and this ADR must be revisited:

1. The tenant constraint can never be empty, absent or widened (CTL-015).
2. Only the gateway may query the retrieval structure; no user-facing, legacy or support component can (CTL-008).
3. Every retrieved result is verified against the authoritative ownership record before any content reaches a model
   (CTL-017).
4. Ownership is assigned only by the ingestion service and cannot change (CTL-011, CTL-013).
5. The cross-tenant negative tests are proven able to detect a missing constraint (TST-SEN-011).

**Always-filter rule.** The tenant constraint is applied to every retrieval **even if a tenant is later placed in a
dedicated or grouped structure**. Moving towards Option C therefore adds a layer of separation; it never replaces the
constraint.

## Why not the other options

- **Why not A (dedicated per tenant)?** It buys blast-radius reduction that no current requirement demands — contracts ask
  for logical segregation — at the price of per-tenant infrastructure that a five-person team would have to provision,
  monitor, patch and keep consistent for 120 → 400 tenants (CON-003, RSK-09). Each tenant would add fixed cost
  (NFR-004). Its routing decision would still need to be protected as carefully as B's constraint, unless each tenant
  also received separately scoped credentials — more machinery again. **A would win** if contracts required physical
  separation, if tenants needed their own encryption keys, or if there were a few dozen very high-value tenants.
- **Why not C (cells) now?** It adds a routing layer, a placement process and several structures before any requirement
  needs them. It is the **planned evolution** of B, triggered by the conditions below.
- **Why not D (per-user access lists)?** It fails the onboarding gate: a tenant boundary expressed as per-user lists on
  every document is exactly the hand-maintained rule set that NFR-002 forbids. The store cannot verify the identity it
  is given, so D is no stronger than B and harder to operate.

## Consequences

**Positive**
- Onboarding is data, not infrastructure: a registry entry plus identity-provider membership (NFR-002, BUS-002).
- One place to observe, test and prove the isolation control; the sensitivity test targets exactly one control.
- Cost follows documents and questions, not tenant count (NFR-004).

**Negative / accepted trade-offs**
- **Shared blast radius:** a defect that bypassed the constraint would expose all tenants. Accepted only because the
  conditions above make that defect require several independent failures, and because TST-SEN-011 shows the tests would
  detect it.
- **One encryption domain** for all tenants' retrieval data; per-tenant keys would require Option A or C. Detailed data
  classification is Episode 02.
- **Noisy neighbour on ingestion:** a very large tenant (ASM-002) can delay other tenants' indexing.
- A future contract that requires physical separation cannot be met without moving that tenant to a dedicated cell.

**Evolution triggers (move specific tenants towards Option C)**
- A customer contract requires physical separation or a dedicated key.
- One tenant's volume or ingestion activity measurably delays other tenants.
- The shared structure approaches a platform limit on size, request rate or ingestion concurrency.
- Shared content is introduced (ASM-007) and needs a structure of its own — see TARGET_ARCHITECTURE section 10.

## Residual risks

RR-04 shared blast radius · RR-05 filter-evaluation defect in the underlying store · RR-06 permission drift ·
RR-13 platform limits as tenants grow. See [RESIDUAL_RISK_REGISTER.md](../03-architecture/RESIDUAL_RISK_REGISTER.md).

## Controls introduced

| ID | Control | Enforcement point |
|---|---|---|
| CTL-001 | **Mandatory owning-tenant attribute.** Every indexed chunk carries exactly one owning-tenant attribute and a document identifier. A chunk without them is never indexed (ingestion refuses) and, if one is ever retrieved, is treated as a violation (retrieval verification) | Retrieval structure schema; ingestion service (CTL-012); retrieval gateway (CTL-017) |
| CTL-002 | **Tenant data protection and placement.** Original documents, derived chunks and embeddings, ownership and registry records, and security audit records are encrypted at rest with keys under Veltamere's control, encrypted in transit, and stored only in the contracted region | Storage and index configuration; deployment review |

## Validation implications

- TST-ISO-003 and TST-ISO-004 exercise the shared structure with same-topic documents from both tenants, so the
  constraint is the only thing that separates them.
- TST-SEN-011 removes the tenant constraint (CTL-015) and must see both negative tests fail — proving that the shared
  model's defining weakness would be detected.
- TST-OPS-017 onboards Tenant C with a registry entry and identity-provider membership only.
- CMP-002 and SEC-011 are verified by configuration review.

## Platform evidence (checked after the decision)

- The implementation environment limits the number of retrieval structures per account and region, and the limit is not
  adjustable (PC-06). Option A would need several accounts from day one to host 120 tenants — **confirming**, not
  causing, the rejection of A.
- The environment supports metadata constraints evaluated during vector search (PC-01, PC-09), which Option B needs.
- Prior art describes the same silo, pool and bridge trade-offs (PC-25).

Sources and dates: [AWS_SERVICE_MAPPING.md — currency check](../03-architecture/AWS_SERVICE_MAPPING.md#4-currency-check).

## Related

- Requirements: SEC-001, SEC-004, DATA-002, NFR-002, NFR-004, CMP-001, CMP-002, SEC-011, BUS-002, NFR-003
- Decisions: ADR-002, ADR-003, ADR-004, ADR-005
- Tests: TST-ISO-003, TST-ISO-004, TST-SEN-011, TST-OPS-017
