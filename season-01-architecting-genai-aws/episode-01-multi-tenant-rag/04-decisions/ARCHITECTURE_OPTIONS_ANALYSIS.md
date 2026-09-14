<!-- template: tla-options-analysis/1 -->
# Architecture Options Analysis — Veltamere Document Assistant

**Stage:** architecture (E2) · **Status:** accepted — architecture approved 2026-09-14 · **Date:** 2026-09-14

This document turns the approved requirements into decisions in a fixed order:

```
REQUIREMENTS → DECISION CRITERIA → CREDIBLE OPTIONS → TRADE-OFFS → DECISION (recorded as an ADR)
```

It is **service-neutral on purpose**. The options are architecture patterns, not products. The patterns were chosen first
and only then mapped to an implementation environment in [AWS_SERVICE_MAPPING.md](../03-architecture/AWS_SERVICE_MAPPING.md).
If you are working through the engagement yourself, answer the [decision questions](ARCHITECTURE_DECISION_QUESTIONS.md)
before reading on.

---

## 1. Decision criteria

Every criterion comes from a requirement, assumption or constraint. **Gate criteria are pass/fail**: an option that fails
one is rejected however well it scores elsewhere. The remaining criteria are trade-offs. **Cost never decides alone.**

| Criterion | What it asks | Derived from | Type |
|---|---|---|---|
| C-01 Tenant isolation strength | Can Tenant A content enter Tenant B's retrieval result, answer, citations or metadata? | SEC-001, SEC-004, DATA-002 | **Gate** |
| C-02 Blast radius | If one control or component is wrong, how many tenants are exposed? | SEC-001, OBJ-3 | Trade-off (high weight) |
| C-03 Identity trust | Is tenant context derived only from verified identity, never from caller input? | SEC-002, SEC-003, CON-004, ASM-004 | **Gate** |
| C-04 Authorisation placement | Is there exactly one authoritative decision, made before retrieval, that no path can skip? | SEC-004, SEC-009 | **Gate** |
| C-05 Ingestion attribution | Is ownership assigned by a trusted component from the uploader's verified tenant? | SEC-006, DATA-001 | **Gate** |
| C-06 Metadata integrity | Can ownership be altered, omitted or diverge from the authoritative record without detection? | SEC-007, DATA-002, DATA-003 | **Gate** |
| C-07 Bypass resistance | Does every path to documents or retrieval data pass the decision? | SEC-009, SEC-010 | **Gate** |
| C-08 Fail-closed behaviour | Does missing or unresolvable context produce no retrieval, never "everything"? | SEC-008 | **Gate** |
| C-09 Observability | Can an investigator reconstruct who, which tenant, which decision, what was retrieved — without content in records? | OPS-001, OPS-002, CMP-001 | Trade-off |
| C-10 Tenant onboarding | Can a tenant be enabled with no code change and no hand-written per-tenant rule? | NFR-002, BUS-002 | **Gate** |
| C-11 Operational burden | What must a five-engineer team run, patch, monitor and keep consistent? | CON-003, NFR-003 | Trade-off (high weight) |
| C-12 Scaling | Does the design hold from 120 towards 400 tenants and the assumed volumes? | ASM-001, ASM-002, ASM-003 | Trade-off |
| C-13 Latency | Does the design leave room for the answer to begin within about 5 seconds? | NFR-001 | Trade-off |
| C-14 Cost structure | Does cost grow with usage rather than with tenant count? | NFR-004, CON-002, CON-008 | Trade-off |
| C-15 Reproducibility | Can the learner implementation be deployed and validated non-interactively? | OPS-003, OPS-005, CON-007 | Trade-off |
| C-16 Learner comprehensibility | Is the isolation control visible and testable, not hidden in machinery? | CON-007 | Trade-off |
| C-17 Production evolution | Can the design absorb stricter contracts, shared content or growth without weakening SEC-001? | ASM-007, CON-002 | Trade-off |
| C-18 Data residency | Do documents, derived data and processing stay in the contracted region? | CMP-002, CON-006 | **Gate** |
| C-19 Testability | Can each boundary be exercised by a negative test that has been seen to fail? | OPS-005, TST-SEN-011 | Trade-off (high weight) |

Ratings used below: **Strong** · **Adequate** · **Weak** · **FAILS GATE**.

---

## 2. Tenant isolation model → ADR-001

**Decision question:** what is the unit of isolation for retrieval data, and is it enforced physically (separate
structures), logically (one structure, enforced partition) or by a mix?

### Option A — Dedicated retrieval structure per tenant ("silo")

Each tenant has its own retrieval index and indexing pipeline. A variant (A′) gives each tenant its own environment or
cloud account.

| Aspect | Analysis |
|---|---|
| What the isolation boundary is | Resource separation: Tenant B's chunks physically live in a different structure. A query can only reach B's content if it is sent to B's structure |
| What must be trusted | The **routing decision** (tenant → structure). Unless each tenant's structure is also protected by a separate credential scoped to that tenant, routing is a software decision exactly as trusted as a filter |
| How tenant identity reaches retrieval | Verified tenant context selects the structure identifier from a mapping |
| If ownership metadata is wrong | A document ingested into the wrong tenant's structure is served to that tenant; there is no second chance to catch it inside the structure |
| If authorisation fails | A routing defect sends a query to one other tenant's structure: **one** other tenant exposed per defect |
| Blast radius | Smallest of all options (one tenant per routing defect; none from filter defects) |
| Operational complexity | Highest: N indexes, N ingestion pipelines, N sets of alarms, keys and capacity settings to keep consistent. A′ multiplies this by environments |
| Onboarding | Provisioning per tenant. Can be automated, but every tenant becomes per-tenant infrastructure configuration that can drift (RSK-09) |
| Scale implications | Resource count grows linearly with tenants (120 → 400). Per-environment limits on the number of retrieval structures become a planning constraint (see ADR-001 platform evidence) |
| Cost structure | Any fixed cost per structure is multiplied by tenant count; small tenants cost as much to host as large ones |
| Observability | Per-tenant signals are natural; cross-tenant investigation requires aggregating N sources |
| Testability | Cross-tenant tests are clear; the sensitivity test must deliberately misroute |
| Failure modes | Misrouting; drift between tenants' configurations; a forgotten tenant structure left unpatched or unmonitored |
| Residual risks | Routing defect; operator error in per-tenant provisioning; cost pressure pushing towards shortcuts |

### Option B — Shared retrieval structure with an enforced tenant partition ("pool")

All tenants' chunks live in one retrieval structure. Every chunk carries exactly one owning-tenant attribute, set at
ingestion. **Every** retrieval is constrained to one tenant by a constraint built server-side from verified tenant
context and evaluated **inside** the search.

| Aspect | Analysis |
|---|---|
| What the isolation boundary is | The tenant constraint evaluated by the retrieval structure during the search, combined with the correctness of each chunk's owning-tenant attribute |
| What must be trusted | Tenant context derivation; the single component that constructs the constraint; ingestion attribution; the guarantee that no other component can query the structure without the constraint |
| How tenant identity reaches retrieval | Verified identity → trusted tenant context → constraint `owning tenant = <that tenant>` attached to the retrieval request |
| If ownership metadata is wrong | The constraint enforces the wrong owner: the document reaches the tenant it is attributed to. Divergence from the authoritative ownership record is detectable at retrieval time |
| If authorisation fails | If the constraint were ever omitted or empty, **every tenant's** content becomes retrievable. This is the defining weakness and must be made impossible by construction, not by care |
| Blast radius | Largest per defect: all tenants in the shared structure |
| Operational complexity | Lowest: one structure, one pipeline, one set of alarms |
| Onboarding | A registry entry and identity-provider membership. No new structure, no code, no rule |
| Scale implications | One structure grows with total content; large tenants can slow shared ingestion ("noisy neighbour") |
| Cost structure | Mostly usage-driven: storage, indexing, queries and generation grow with documents and questions, not tenants |
| Observability | One place to observe every retrieval; the constraint applied can be recorded per request |
| Testability | The primary control is a single, named constraint — the sensitivity test can remove exactly that and watch the negative tests fail |
| Failure modes | Omitted or widened constraint; a second component querying the structure; wrong attribution; filter evaluation defect in the structure itself |
| Residual risks | Shared blast radius; dependency on the constraint-building code path staying the only path |

### Option C — Grouped cells or tiered hybrid ("bridge")

Tenants are placed into a small number of shared cells (by size, contract tier or growth). Each cell is a shared
structure with the tenant partition of Option B. Tenants with contractual demands may get a dedicated cell.

| Aspect | Analysis |
|---|---|
| What the isolation boundary is | Two layers: routing to the tenant's cell, then the tenant constraint inside the cell |
| What must be trusted | The cell assignment record and routing, plus everything Option B trusts |
| How tenant identity reaches retrieval | Verified tenant context → cell lookup → constraint inside the cell |
| If ownership metadata is wrong | As Option B, limited to the cell |
| If authorisation fails | An omitted constraint exposes the tenants in one cell; a routing defect exposes a neighbouring cell (still constrained, if the always-filter rule holds) |
| Blast radius | Bounded by cell size |
| Operational complexity | Medium: K cells, a placement process, rebalancing when a cell fills |
| Onboarding | Registry entry plus automated cell assignment — data, not code |
| Scale implications | Scales by adding cells; isolates a very large tenant from the rest |
| Cost structure | Fixed cost per cell plus usage |
| Observability | Per-cell and per-tenant; requires correlating cell with tenant |
| Testability | Needs cross-cell and within-cell negative tests; two sensitivity runs (routing and constraint) |
| Failure modes | Mis-assignment; uneven cells; migration errors when moving a tenant |
| Residual risks | More moving parts for a small team before a requirement demands them |

### Option D — Shared structure with store-enforced per-user access lists

Documents carry access lists naming the users allowed to read them; the retrieval structure filters results for a user
identity supplied with each query.

| Aspect | Analysis |
|---|---|
| What the isolation boundary is | The store's evaluation of per-document access lists against **an identity the caller passes in** |
| What must be trusted | The application that supplies the user identity (the store cannot verify it), and the correctness of every per-document list |
| How tenant identity reaches retrieval | Not directly — the tenant boundary is emulated by listing each tenant's users on each of that tenant's documents |
| If ownership metadata is wrong | A wrong list exposes the document to whoever is listed |
| If authorisation fails | A wrong user identity passed to the store yields that user's documents; the store has no independent check |
| Blast radius | All documents reachable by the identity supplied |
| Operational complexity | Medium to high: every membership change means updating lists on every document of that tenant |
| Onboarding | Lists written for every user on every document — **hand-maintained per-user rules** |
| Scale implications | List maintenance grows with users × documents |
| Cost structure | Usage-driven, plus re-indexing when memberships change |
| Observability | Store-side filtering can be opaque: missing entries silently return fewer results |
| Testability | Testable, but a mismatch looks like "no results" rather than an error |
| Failure modes | Stale lists after a user leaves; lists that diverge from the identity provider |
| Residual risks | Membership drift; a tenant boundary that exists only as the sum of many lists |

### Comparison

| Criterion | A — dedicated per tenant | B — shared, enforced partition | C — cells / tiers | D — per-user access lists |
|---|---|---|---|---|
| C-01 Isolation strength (gate) | Strong | Adequate — **only** with the conditions in ADR-001 | Adequate+ | Adequate |
| C-02 Blast radius | Strong | Weak | Adequate | Weak |
| C-03 Identity trust (gate) | Pass | Pass | Pass | Pass only if the application verifies identity |
| C-04 Authorisation placement (gate) | Pass | Pass | Pass | Pass |
| C-05 / C-06 Attribution and integrity (gate) | Pass | Pass | Pass | Pass, with per-user lists |
| C-07 Bypass resistance (gate) | Pass | Pass only with exclusive retrieval permission | Pass | Pass |
| C-08 Fail-closed (gate) | Pass | Pass only if the constraint cannot be empty | Pass | Pass |
| C-10 Onboarding without per-tenant rules (gate) | Adequate (per-tenant infrastructure) | Strong | Strong | **FAILS GATE** — per-user lists maintained per document |
| C-11 Operational burden | Weak | Strong | Adequate | Adequate |
| C-12 Scaling 120 → 400 | Weak | Strong (watch ingestion contention) | Strong | Weak |
| C-13 Latency | Strong | Strong | Strong | Adequate |
| C-14 Cost structure | Weak (fixed cost × tenants) | Strong | Adequate | Adequate |
| C-16 Learner comprehensibility | Adequate (control hidden in routing) | Strong (one visible constraint) | Adequate | Weak |
| C-17 Production evolution | Weak for shared content | Strong — can evolve into C without changing the rule | Strong | Adequate |
| C-18 Data residency (gate) | Pass | Pass | Pass | Pass |
| C-19 Testability | Adequate | Strong | Adequate | Adequate |

### Outcome

**Option B is chosen, with mandatory conditions** → [ADR-001](ADR-001-tenant-isolation-model.md).

**The trade-off is not hidden.** Stronger physical separation (A) reduces cross-tenant blast radius but multiplies
resources, operations, onboarding work, cost and lifecycle management. Shared logical isolation (B) improves efficiency,
onboarding and utilisation, but it makes identity, authorisation, attribution, retrieval filtering and bypass prevention
**far more critical**, because one missing constraint would expose everyone. Neither is universally superior. B wins
**here, under the present assumptions**:
- the contractual requirement is tenant segregation, and the decision concludes that enforced logical isolation satisfies
  it;
- dedicated physical infrastructure per tenant is not currently required;
- the shared platform is an explicit constraint;
- the team is small;
- onboarding must need no per-tenant infrastructure or rules;
- cost must follow usage as tenants grow from about 120 towards about 400.

It is only acceptable because the architecture removes its defining weakness by construction:
- the constraint cannot be empty (CTL-015);
- only one component may retrieve (CTL-008);
- results are verified against ownership before generation (CTL-017);
- the sensitivity test proves the negative tests detect a missing constraint (TST-SEN-011).

- **A not chosen:** it genuinely reduces blast radius, which matters even though it is not a numbered requirement. But
  dedicated per-tenant infrastructure is not currently required. At about 120 → 400 tenants it would materially increase
  resource count, lifecycle operations and fixed cost for a small team (CON-002, CON-003, NFR-002, NFR-004). Its routing
  decision is still a software decision unless every tenant also gets separately scoped credentials. With C, it remains
  the escalation path if requirements change.
- **C deferred, not rejected:** it adds a routing layer and K structures before any requirement needs them. It is the
  **defined evolution** of B (ADR-001 triggers), and the always-filter rule means moving to C never weakens SEC-001.
- **D rejected:** it fails the onboarding gate (per-user lists on every document) and cannot verify the identity it is
  given, so it is no stronger than B while being harder to operate.

---

## 3. Tenant context source → ADR-002

**Decision question:** where does tenant context come from, and which component is trusted to establish it?

| Option | How it works | Assessment |
|---|---|---|
| A — Caller-supplied tenant ID | The request names the tenant (the legacy export pattern) | **FAILS GATE C-03** (SEC-003). Any authenticated user could name any tenant |
| B — Verified token claim | Tenant taken from a claim in a token whose signature, issuer, audience, expiry and type are verified | Strong on C-03 if the claim is issued from administrator-controlled membership. Cannot see a tenant disabled after the token was issued |
| C — Server-side membership lookup | Tenant resolved by looking up the verified user identifier in a membership store the platform holds | Strong on C-03, but duplicates membership that CON-004 keeps authoritative in the identity provider, creating a second copy that can drift |
| D — Verified claim **validated against the tenant registry** | B, plus a server-side check that the claimed tenant exists and has the assistant enabled | Strong on C-03 and C-08; supports BUS-001 immediately; keeps membership authority with the identity provider |

**Chosen: D** → [ADR-002](ADR-002-trusted-tenant-context.md).

---

## 4. Authorisation enforcement point → ADR-003

**Decision question:** where is the authoritative decision "this user may retrieve from this tenant's documents" made,
and which later controls are defence in depth?

| Option | How it works | Assessment |
|---|---|---|
| A — API edge only | The edge verifies the token and allows the request | Authenticates, but cannot constrain **what is retrieved**; the retrieval call happens behind it. Fails C-04 as the sole point |
| B — Dedicated authorisation service | The application asks a separate policy decision point, then builds the retrieval constraint | Credible and valuable for rich policies. Today there is one rule ("a member may query their own tenant"); a separate service adds a dependency and splits the decision from the constraint that enforces it |
| C — Retrieval gateway | One application component is the **only** caller of retrieval; it makes the decision and builds the constraint in the same code path from the same tenant context | Strong on C-04 and C-07; the decision and its enforcement cannot disagree |
| D — Store-native policy | The retrieval structure enforces access itself | Only as strong as the identity passed to it; the store cannot verify end users (see Option D above) |
| E — Every layer "kind of" checks | Edge, service and store each check something; none is authoritative | Rejected by design: when every layer partly checks, each assumes another is the real control, and nobody can say which test proves isolation |

**Chosen: C as the authoritative point**, with named secondary layers → [ADR-003](ADR-003-authorisation-enforcement-point.md).

---

## 5. Document tenant attribution → ADR-004

| Option | How it works | Assessment |
|---|---|---|
| A — Uploader chooses the tenant | A form field or metadata value selects the owner | **FAILS GATE C-05** (SEC-006) |
| B — Derived from storage location only | The folder or key prefix implies the owner | Useful as a cross-check, but anything able to write to the location can create ownership, and the location alone is not a record |
| C — Assigned by the ingestion service from the uploader's verified tenant | The trusted service assigns the owner, generates the document identifier, writes the ownership record and passes the owner to indexing | Strong on C-05; ownership has one authoritative source |
| D — Derived from document content | Detect tenant names or labels inside the document | Rejected: content is untrusted input; a document can claim anything |
| E — Editable by customer administrators | Owners can be changed in the product | **FAILS GATE C-06** (SEC-007) |

**Chosen: C, cross-checked against B, with a consistency gate, quarantine and immutable attribution** →
[ADR-004](ADR-004-document-tenant-attribution.md).

---

## 6. Retrieval boundary → ADR-005

| Option | How it works | Assessment |
|---|---|---|
| A — Tenant constraint evaluated inside every retrieval | The constraint is part of the search, so non-matching chunks are never candidates | Strong on C-01 and C-08 when the constraint cannot be empty |
| B — Select a tenant-specific structure | Routing instead of constraint | Belongs to isolation Options A and C; not needed for the chosen shared model |
| C — Remove other tenants' results after retrieval | Retrieve broadly, then filter | **FAILS GATE C-01** (SEC-004): content has already crossed the boundary. Allowed only as verification (defence in depth), never as the control |
| D — Prompt instruction to use only the tenant's documents | The model is told what not to use | **FAILS GATE C-01** (SEC-005) |
| E — A model generates the retrieval constraint from the question | The question text shapes the scope | **FAILS GATE C-01** (SEC-005): persuasion would change scope |
| F — Redact the generated answer | Scan and remove other tenants' information from answers | **FAILS GATE C-01** (SEC-004): retrieval and generation have already happened |

**Chosen: A, with post-retrieval verification as defence in depth only** → [ADR-005](ADR-005-retrieval-boundary.md).

---

## 7. Audit and observability → ADR-006

| Option | How it works | Assessment |
|---|---|---|
| A — Platform API activity records only | Rely on the cloud provider's record of API calls | Records the **service's** identity, not the end user or tenant; cannot answer "who asked in which tenant" |
| B — Log full requests and responses | Capture questions, retrieved text and answers | **Fails OPS-002**: the logs become a second copy of confidential data |
| C — One content-free security audit record per request, written by the authorising component | Correlation ID, user, tenant context, decision, reason, constraint applied, retrieved document IDs and owners, verification outcome | Answers OPS-001 without content |
| D — Retrieval-layer access logs only | Log what the store returned | Misses refused requests and the reason for a decision |

**Chosen: C, plus platform activity records used only to detect bypass (a retrieval by any other principal)** →
[ADR-006](ADR-006-audit-and-observability.md).

---

## 8. Model invocation boundary and data residency → ADR-007

This decision was not one of the E1 decision questions. It became architecture-significant during analysis, because
**where retrieval and generation meet** determines whether there is any point at which retrieved content can be verified
before a model sees it.

| Option | How it works | Assessment |
|---|---|---|
| A — Combined retrieve-and-generate step | One call retrieves and generates; citations come back from the store | Keeps the constraint, but removes the checkpoint between retrieval and generation, and returns storage locations and metadata as citations |
| B — Separate retrieval, verification, then generation | The gateway retrieves, verifies ownership, builds citations and only then invokes the model with the verified context | Strong on C-01 (verification before generation) and citation control |
| C — Model with a retrieval tool | The model decides when and what to retrieve | Rejected for this episode: scope decisions move towards the model (SEC-005), and calls multiply |
| Processing location | In-region processing only, versus routing inference to other regions for capacity | Routing to other regions **fails gate C-18** (CMP-002) |

**Chosen: B, in-region only** → [ADR-007](ADR-007-model-invocation-boundary.md).

---

## 9. Neutrality check

- Every option above is a pattern. No option was introduced because a product offers it.
- Where platform facts are cited in an ADR, they appear under **"Platform evidence (checked after the decision)"** and
  either confirm a pattern-level decision or add a control. **No decision would be different if those facts were
  absent**, with one exception recorded openly: the platform evidence that a retrieval permission cannot be restricted
  per tenant **added** controls (CTL-008, CTL-013) to ADR-003 and ADR-004; it did not change which option was chosen.
