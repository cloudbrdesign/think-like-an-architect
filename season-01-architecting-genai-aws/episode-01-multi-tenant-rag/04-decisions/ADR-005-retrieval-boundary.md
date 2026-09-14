<!-- template: tla-adr/1 -->
# ADR-005 — Retrieval boundary: a mandatory tenant constraint evaluated inside every search

**Status:** proposed — awaiting architecture approval · **Date:** 2026-09-14
**Answers:** decision question DQ-E · **Options analysis:** [section 6](ARCHITECTURE_OPTIONS_ANALYSIS.md#6-retrieval-boundary--adr-005)

## Context

**The key question of this episode:** what technical boundary prevents Tenant A content from entering Tenant B's
retrieval result? In the shared structure (ADR-001) both tenants' chunks sit side by side, often on the same topics.
The boundary must hold before any content reaches generation, must not depend on the model, and must fail closed.

## Requirements driving this decision

- **SEC-001** (invariant) — nothing of Tenant B in results, answers, citations or metadata.
- **SEC-004** (invariant) — no other tenant's content enters retrieval results or model context; removal afterwards does
  not satisfy the requirement.
- **SEC-005** (invariant) — instructions in questions or documents cannot widen scope.
- **SEC-008** (invariant) — missing constraint → no retrieval.
- **DATA-002** — nothing derived from a document is retrievable outside its tenant.
- **FUN-001**, **FUN-003** — cited answers from the tenant's own documents; deleted documents stop being retrieved.
- Risks: RSK-01, RSK-03, RSK-05, RSK-06, RSK-11, RSK-14, RSK-15.

## Options considered

| Option | Where scope is enforced | Verdict |
|---|---|---|
| **A — Constraint evaluated inside every retrieval** | Retrieval structure, during search, from a gateway-built constraint | Chosen |
| B — Select a tenant-specific structure | Routing | Belongs to isolation options A and C |
| C — Filter results after retrieval | After content has left the structure | Fails SEC-004 as a control; kept only as verification |
| D — Prompt instruction | Inside the model | Fails SEC-005 |
| E — Model-generated constraint from the question | The model | Fails SEC-005 |
| F — Redact generated answers | After generation | Fails SEC-004 |

**Explicitly rejected as isolation mechanisms:** isolation in the prompt, isolation after retrieval, isolation during
answer generation, isolation through model instructions.

## Trade-offs

Evaluating the constraint inside the search means non-matching chunks are never candidates, so nothing from another
tenant is ever returned. The cost is that the search must support attribute constraints, and that a very selective
constraint in a very large shared structure can return fewer relevant results than an unconstrained search (a recall
issue, not a leak). Verification after retrieval cannot replace the constraint, but it can **detect** a broken constraint
or attribution before generation.

## Decision

### Primary isolation control

1. For every retrieval, the gateway attaches the constraint **`owning_tenant EQUALS <tenant context tenant_id>`**
   (CTL-015).
2. The constraint builder accepts **only** a tenant context produced by the resolver. It has **no code path** that
   returns an empty, absent, wildcard, `OR` or multi-value constraint. If it cannot build a single-tenant equality
   constraint, it raises, and the request is **denied** (`CONSTRAINT_UNBUILDABLE`) — no retrieval call is made.
3. The constraint is **combined with nothing the caller controls.** Result count, search type and any other retrieval
   parameters are fixed server-side.
4. **Always-filter rule** (ADR-001): the constraint is applied even when a future tenant has its own structure.

### No model-influenced scope

5. The question text is used **only** as the semantic query. No model generates or edits constraints, no query rewriting
   can change the constraint, and there is no agent or tool-driven retrieval (CTL-016).

### Defence in depth: verify before generation

6. The gateway verifies **every** result before any content reaches a model (CTL-017):
   - the result carries an owning-tenant attribute equal to the tenant context; and
   - the ownership record for its document identifier exists, names the same owner, and has status `AVAILABLE`.
7. **Owner mismatch or missing owner** → the **entire response is withheld**, a generic error is returned, and a
   security event `OWNERSHIP_MISMATCH` is recorded. A mismatch means the primary control or attribution is broken, so
   nothing from that request is trusted.
8. **Status not `AVAILABLE`** (deleting, deleted, quarantined) → that result is discarded; the others continue. This
   is freshness, not isolation.
9. This verification **does not satisfy SEC-004** and is not presented as doing so. It exists to detect failure of
   CTL-015 or CTL-011 and to stop a detected failure from reaching generation.

### Citations are data disclosure

10. Citations are built **by the gateway** from verified results only. A citation exposes the document identifier and
    the tenant's own document title (and a page or section where available) — **never** a storage location, index
    identifier, score or raw metadata. References in model output that do not map to a verified result are removed
    (CTL-018).

### Every output channel

| Output channel | How another tenant's information is kept out |
|---|---|
| Retrieval results | CTL-015 (primary) · CTL-017 verification |
| Model context | Only verified results enter it (CTL-017, CTL-022) |
| Generated answer | The model sees only the verified context of the caller's tenant (CTL-022) |
| Citations and source metadata | Built only from verified results; no storage locations or raw metadata (CTL-018) |
| Error messages | Generic; another tenant's document identifier behaves as not found (CTL-014) |
| Security audit records | Content-free; internal to Veltamere (CTL-019, CTL-020) |
| Logs and model invocation logs | No bodies or content (CTL-020, CTL-024) |
| Caches | No shared response cache in this design (CTL-022) |

## Why not the other options

- **Why not filter after retrieval (C)?** The other tenant's content would already have left the retrieval structure.
  SEC-004 exists precisely because "we removed it afterwards" means the boundary was crossed. Verification is kept only
  as a detector.
- **Why not a prompt instruction (D)?** Models can be persuaded; TST-SEC-006 exists to prove the prompt is not the
  control.
- **Why not a model-generated constraint (E)?** It would let the question text shape the scope of retrieval — exactly
  what SEC-005 forbids.
- **Why not redaction (F)?** Detecting another company's information in free text is unreliable, and retrieval and
  generation have already happened.

## Consequences

**Positive**
- The boundary is one inspectable constraint, built in one place, from one trusted input.
- A missing tenant fails closed by construction rather than by convention.
- Divergence between index and ownership record is caught on every request.

**Negative / accepted trade-offs**
- One ownership-record read per result (latency; NFR-001 review).
- Withholding the whole response on mismatch turns a detected defect into an outage for that request. Accepted:
  availability yields to isolation.
- Recall can drop for very selective constraints in a very large shared structure; watched through pilot measurement
  (RR-13).

## Residual risks

RR-04 shared blast radius · RR-05 defect in the store's evaluation of constraints · RR-10 answer integrity under indirect
prompt injection.

## Controls introduced

| ID | Control | Enforcement point |
|---|---|---|
| CTL-015 | **Mandatory tenant constraint (primary isolation control).** Every retrieval carries `owning_tenant EQUALS tenant_id` built only from resolver-produced tenant context; empty, absent, wildcard or multi-value constraints are impossible and cause denial; all other retrieval parameters are fixed server-side | Retrieval gateway (constraint builder); evaluated by the retrieval structure during search |
| CTL-016 | **No model-influenced retrieval scope.** Question text is only the semantic query; no model-generated constraints, no scope-changing query rewriting, no agent or tool retrieval, no caller-supplied retrieval parameters | Retrieval gateway |
| CTL-017 | **Ownership verification before generation (defence in depth).** Each result's owner attribute and ownership record must match the tenant context with status `AVAILABLE`; mismatch withholds the entire response and records `OWNERSHIP_MISMATCH`; non-available results are discarded | Retrieval gateway, between retrieval and generation |
| CTL-018 | **Citation isolation.** Citations only from verified results, exposing document identifier, own title and location within the document; no storage locations, index identifiers, scores or raw metadata; unmapped model references removed | Retrieval gateway (answer composer) |

## Validation implications

- **Primary observation point for isolation tests is the retrieval layer**, recorded in the content-free security audit
  record (retrieved document identifiers and their owners), not the model's answer.
- TST-ISO-003 / TST-ISO-004 · TST-SEN-011 removes CTL-015 · TST-SEC-006 and TST-SEC-008 · TST-SEC-013 (constraint cannot
  be built) · TST-SEC-021 citations · TST-SEC-022 verification · TST-DATA-014 deletion.

## Platform evidence (checked after the decision)

- The retrieval API accepts an equality constraint on document attributes with each request (PC-01), and the chosen
  vector store evaluates constraints **during** the search rather than after it (PC-09).
- The environment also offers **implicit filtering**, where a model generates the constraint from the user's query
  (PC-02). **CTL-016 forbids it.**
- Retrieval results include storage locations and metadata by default (PC-14) — hence CTL-018.
- An alternative store applies constraints after its index scan unless configured otherwise, which can reduce recall
  (PC-11) — one reason it was not selected.

## Related

- Requirements: SEC-001, SEC-004, SEC-005, SEC-008, DATA-002, FUN-001, FUN-003
- Decisions: ADR-001, ADR-003, ADR-004, ADR-007
- Tests: TST-ISO-003, TST-ISO-004, TST-SEN-011, TST-SEC-006, TST-SEC-008, TST-SEC-013, TST-SEC-021, TST-SEC-022, TST-DATA-014
