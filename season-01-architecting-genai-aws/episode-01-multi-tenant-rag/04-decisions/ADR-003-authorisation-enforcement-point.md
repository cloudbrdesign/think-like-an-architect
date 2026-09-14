<!-- template: tla-adr/1 -->
# ADR-003 — Authorisation enforcement point: the retrieval gateway is authoritative

**Status:** accepted — architecture approved 2026-09-14 · **Date:** 2026-09-14
**Answers:** decision question DQ-C · **Options analysis:** [section 4](ARCHITECTURE_OPTIONS_ANALYSIS.md#4-authorisation-enforcement-point--adr-003)

## Context

With a shared retrieval structure (ADR-001), the decision "this user may retrieve from this tenant's documents" and the
constraint that enforces it are the heart of the design. A common failure is a layered design in which the edge, the
service and the store each check *something* about the tenant, none is authoritative, and nobody can say which test
proves isolation. This ADR names **one** authoritative point and states what every other layer is for.

## Requirements driving this decision

- **SEC-004** (invariant) — authorisation decided before any content is retrieved.
- **SEC-009** — no route reaches documents or retrieval data without passing the decision.
- **SEC-010** — least privilege; no user-facing component can read every tenant's documents.
- **SEC-008** (invariant) — fail closed.
- **SEC-002** — authenticated identity on every question.
- Risks: RSK-02, RSK-03, RSK-07, RSK-08.

## Options considered

| Option | Where the authoritative decision sits | Verdict |
|---|---|---|
| A — API edge only | Token check at the edge | Authenticates; cannot constrain what is retrieved |
| B — Dedicated authorisation service | Separate policy decision point consulted by the application | Credible; premature for one rule, and separates the decision from the constraint |
| **C — Retrieval gateway** | The only component allowed to retrieve decides and builds the constraint in one code path | Chosen |
| D — Store-native policy | The retrieval structure decides | The store cannot verify end users |
| E — Several partial checks | Nowhere | Rejected by design |

## Trade-offs

A dedicated authorisation service centralises policy and scales to rich rules, but it adds a network dependency and a
translation step (decision → constraint) that is itself security-critical. Putting the decision in the gateway keeps the
decision and its enforcement in one place, at the cost of re-architecting when policies become rich. Episode 01 has one
policy; the trade-off favours the gateway now, with a named trigger for change.

## Decision

**The retrieval gateway, inside the query service, is the authoritative enforcement point for reading tenant content.**

1. It receives the tenant context built by the resolver (ADR-002) — never a tenant value from the request.
2. It decides **ALLOW** only when the tenant context is valid and the action (`ask`) is permitted for a member of an
   enabled tenant. Otherwise **DENY**, with a reason code (CTL-007).
3. **Only on ALLOW** does it construct the tenant constraint (ADR-005). Decision and constraint are produced by the same
   function from the same tenant context, and the retrieval client accepts only the tenant-scoped query that function
   returns. There is no retrieval call that bypasses this function.
4. **It is the only principal permitted to query the retrieval structure** (CTL-008).
5. The **ingestion service** is the equivalent authoritative point for **writing** tenant content (ADR-004), using the
   same resolver.
6. The services are reachable **only through the API edge**. A direct invocation that bypasses the edge, carrying a
   forged claim set, is refused by the platform before service code runs (CTL-009).
7. **Privileged operations** — correcting attribution, investigating an incident — use a separate operator role that is
   not reachable from tenant-facing routes, and every use is recorded (CTL-010).

### Every layer and its role

| Layer | Role | Authoritative for isolation? |
|---|---|---|
| API edge token verification (CTL-003) | Authentication: rejects missing and invalid tokens early | No — prerequisite |
| Tenant Context Resolver (CTL-004, CTL-005) | Turns verified claims into trusted tenant context | No — prerequisite |
| **Retrieval gateway decision + constraint (CTL-007, CTL-015)** | **Decides and enforces the tenant scope of retrieval** | **Yes — the primary control** |
| Exclusive retrieval permission (CTL-008) | Structural: no other component can retrieve | No — makes the gateway unavoidable |
| Store evaluation of the constraint | Executes the gateway's constraint during search | No — executes, does not decide |
| Ownership verification before generation (CTL-017) | Detects a broken constraint or attribution; withholds the response | No — defence in depth |
| Bypass detection alert (CTL-021) | Detects retrieval by any other principal | No — detective |
| Prompt instructions to the model | Answer quality only | **Never a control** (SEC-005) |

## Why not the other options

- **Why not the API edge (A)?** The edge proves who is calling. It cannot constrain which chunks a search returns; that
  happens behind it. An edge-only design leaves the shared structure's weakness unprotected.
- **Why not a dedicated authorisation service (B) now?** Today there is a single rule. A separate service would add a
  runtime dependency (and a fail-closed outage mode) while the security-critical step — turning a decision into a
  constraint — would still live in the gateway. **Trigger to adopt B:** shared content, administrator-only content,
  per-user permissions or policies owned by customers (TARGET_ARCHITECTURE section 10). The gateway would then build its
  constraint from the policy service's decision.
- **Why not store-native policy (D)?** The store evaluates whatever identity it is given and cannot verify it. It would
  make the gateway authoritative anyway, while hiding the rule inside store configuration.
- **Why not several partial checks (E)?** When every layer "kind of" checks, each assumes another is the real control,
  regressions go unnoticed, and no single sensitivity test can prove isolation.

## Consequences

**Positive**
- One named place where isolation is decided and enforced; one sensitivity test that removes exactly that control.
- Bypass analysis becomes a permission question: who, other than the gateway, can retrieve? Answer: nobody.

**Negative / accepted trade-offs**
- The gateway's constraint function is the most security-critical code in the system; changes need review and the full
  isolation suite (OPS-005).
- Rich future policies require introducing a policy decision point (trigger above).
- Retrieval permissions in the implementation environment are coarse (next section), so exclusivity must be enforced and
  checked continuously (RR-06).

## Residual risks

RR-02 privileged operator access · RR-04 shared blast radius · RR-06 permission drift · RR-07 legacy export endpoint.

## Controls introduced

| ID | Control | Enforcement point |
|---|---|---|
| CTL-007 | **Authoritative decision and constraint in one code path.** ALLOW only for a valid tenant context and a permitted action; the tenant-scoped query is produced by the same function that decided, and is the only input the retrieval client accepts; DENY carries a reason code | Retrieval gateway (query service) |
| CTL-008 | **Exclusive retrieval permission.** Only the retrieval gateway's runtime identity may query the retrieval structure; no user-facing, legacy, support or batch component holds that permission; direct access to the underlying vector data is limited to the indexing service itself | Permission policies on the retrieval structure and vector data |
| CTL-009 | **Services reachable only through the API edge.** Query and ingestion services refuse invocation by any caller other than the API edge, so a verified claim set cannot be forged by invoking a service directly | Service invocation policy |
| CTL-010 | **Separated privileged operations.** Attribution correction and incident investigation use a distinct operator role, unreachable from tenant-facing routes; every use is recorded | Operator role and runbook; security audit record |

## Validation implications

- TST-SEC-009 attempts every bypass in [TARGET_ARCHITECTURE section 7](../03-architecture/TARGET_ARCHITECTURE.md#7-bypass-analysis).
- TST-SEC-023 checks permission exclusivity by policy analysis: only the gateway can retrieve; only ingestion can index.
- TST-SEC-013 covers deny paths; TST-ISO-003 and TST-ISO-004 prove the constraint.
- SEC-010 is additionally reviewed against every component's permissions.

## Platform evidence (checked after the decision)

- In the implementation environment, **anyone holding the retrieval permission can retrieve everything that has been
  indexed** (PC-04), and the published permission conditions do not allow restricting a retrieval to one tenant's filter
  (PC-05). This did not change the decision; it made **CTL-008 mandatory** and added **CTL-021** detection.
- Retrieval calls can be recorded as data events, with additional charges (PC-22) — used for bypass detection.

## Related

- Requirements: SEC-002, SEC-004, SEC-008, SEC-009, SEC-010
- Decisions: ADR-002, ADR-004, ADR-005, ADR-006
- Tests: TST-SEC-009, TST-SEC-013, TST-SEC-023, TST-ISO-003, TST-ISO-004
