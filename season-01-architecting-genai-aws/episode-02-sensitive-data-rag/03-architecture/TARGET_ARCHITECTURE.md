# Target Architecture — Kestrelmoor Knowledge Assistant

**Status:** accepted (2026-09-15). It follows the accepted ADR-001 to ADR-006.

**Service-neutral:** implementation technology is chosen only after the architecture is approved.

---

## 1. The Episode 02 security invariant (approved)

> **A section reaches generation only if its owner-assigned classification and scope, as currently recorded, match an
> entitlement the requester holds at the moment of the request — decided outside the model, enforced inside the search,
> re-checked before generation. Content that no use case needs is never indexed.**

The chain, stage by stage:

```
Owner-assigned label        Entitlements resolved       Eligibility decided        Mandatory eligibility        Current classification     Generation
at the source           →   per request from        →   outside the model      →   constraint inside the    →   re-verified before     →   (verified chunks
(records system;            authoritative sources       (label + scope vs          right search tier            the model                   only)
 special-category           (HR status, registry)       memberships/cases)         (shared / restricted)
 never indexed)
```

**What makes it different from Episode 01.** Episode 01's chain had one attribute and one answer: *which tenant?*

| | Episode 01 (tenant boundary) | Episode 02 (eligibility boundary) |
|---|---|---|
| What is decided | Which tenant's content | Which **sections** of the organisation's own content |
| Where sensitivity enters | Not at all — everything a tenant owns is theirs | At the source, from the owner's section-level label |
| Where authorization is authoritative | The tenant registry, one membership | HR status and entitlement registry, many memberships and case assignments, resolved per request |
| What the boundary evaluates | `owning_tenant = tenant` | `label` and `scope` against the requester's current entitlements |
| Topology | One shared structure | Tiered by blast radius: shared tier (INTERNAL, CONFIDENTIAL) and restricted tier (RESTRICTED) |
| What is never indexed | — | Special-category content |
| What the check before the model compares | Owner in the ownership record | **Current** classification and scope (catches stale and corrupted labels) |

**Memorable form:** *authenticated is not authorised; authorised for a document is not authorised for every section.*

**Approved security thesis (2026-09-15):**
- Authenticated is not authorised.
- Authorised for a document is not authorised for every section.
- The model is not the authorization authority.
- Prompt instructions are not the authorization boundary.
- **No authoritative current grants = no retrieval.**

**D3 has two layers, and they must not be conflated:**

| Layer | What it is | What it answers | What it does not answer |
|---|---|---|---|
| 1 — Blast-radius reduction (defence in depth) | Tiered structures: shared (INTERNAL, CONFIDENTIAL), restricted (RESTRICTED) | What a single structure contains, and therefore what one defect can expose | Whether this requester may retrieve this section |
| 2 — Authorization enforcement | Mandatory eligibility constraints built from the authoritative current decision, evaluated inside each tier | What this requester may retrieve | — |

**The tier is not the authorization boundary.** Selecting the correct tier grants nothing: the shared tier holds many
access domains, the restricted tier holds many cases, and only the constraint separates them (TST-ELG-009).

---

## 2. Components (logical)

| Component | Responsibility | Trusts | Rejects |
|---|---|---|---|
| Edge | Verify the token; pass only the verified employee identifier | The identity provider's signature, issuer, audience, expiry | Everything else from the client as authorization input |
| Policy decision point | Resolve status, memberships and cases; compute the eligibility decision; record source versions | HR system, entitlement registry | Token group claims, request fields, question text |
| Retrieval gateway | Build the mandatory constraint(s) from the decision; call only the tiers the decision allows; refuse if it cannot build a complete constraint | The policy decision point's decision | Any other constraint source |
| Shared search tier | Hold INTERNAL and CONFIDENTIAL chunks; evaluate the constraint during search | The gateway | Unconstrained queries (by permission) |
| Restricted search tier | Hold RESTRICTED chunks; evaluate the case constraint during search | The gateway, only for requests with case assignments | Every other caller |
| Verification | Re-check every retrieved chunk against the current classification record and the decision; withhold on mismatch | Classification record (current version), decision | Chunk metadata as the final word |
| Generation | Produce an answer from verified chunks and fixed instructions | Nothing: its output is untrusted | Any role in authorization |
| Response builder | Section-level citations from verified chunks only; uniform "cannot answer" response | Verification result | Existence hints |
| Ingestion | Read the document and its classification record; validate; exclude special-category; chunk within sections; route by label; record provenance | Records-system classification record | Labels inside document text |
| Audit | Content-free decision records | — | Content, excerpts, answer text, question text |

---

## 3. Flows

**Ingestion (I1–I6)**
1. **I1** — The records system publishes a document version and its classification record (document label plus section marks).
2. **I2** — Ingestion reads the classification record — never labels from text — and validates the taxonomy and
   label/scope consistency. Invalid documents or sections are excluded and reported (CTL-006, CTL-007).
3. **I3** — Sections carrying a special-category mark are removed before any chunking, embedding or model call (CTL-009).
4. **I4** — Remaining content is chunked **within** section boundaries; each chunk gets the effective label and scope,
   never less restrictive than the document (CTL-008).
5. **I5** — INTERNAL and CONFIDENTIAL chunks go to the shared tier; RESTRICTED chunks go to the restricted tier only
   (CTL-010).
6. **I6** — Each chunk records document, section, label, scope and classification-record version (DATA-007).

**Query (Q1–Q10)**
1. **Q1** — Client sends a question with an access token.
2. **Q2** — Edge verifies the token; invalid means refused, with no downstream call (CTL-002).
3. **Q3** — Policy decision point resolves employment status, domain memberships and case assignments from the
   authoritative sources. Unresolvable means fail closed (CTL-003, CTL-004).
4. **Q4** — Policy decision point computes eligibility: `INTERNAL`, plus the `CONFIDENTIAL` domains held, plus the
   `RESTRICTED` cases assigned (CTL-001).
5. **Q5** — Gateway builds the mandatory constraints (CTL-011, CTL-012, CTL-013):
   - **shared tier:** `label = INTERNAL OR (label = CONFIDENTIAL AND domain ∈ memberships)`;
   - **restricted tier** (only if cases are assigned): `label = RESTRICTED AND case ∈ assignments`;
   - **no complete constraint:** no retrieval call.
6. **Q6** — Each queried tier evaluates its constraint during search; ineligible chunks are never candidates.
7. **Q7** — Verification re-checks every chunk against the current classification record and the decision; any
   mismatch withholds the whole answer and records a security event (CTL-014).
8. **Q8** — Generation receives verified chunks and fixed instructions only.
9. **Q9** — Response carries section-level citations from verified chunks. When nothing eligible answers — or the answer
   is withheld — the response is uniform and reveals nothing about restricted content (CTL-015, CTL-016). Answers that
   use CONFIDENTIAL or RESTRICTED content are never cached (CTL-017).
10. **Q10** — Content-free audit record: decision, source versions, labels and scope IDs, outcome (CTL-018, CTL-019,
    CTL-020).

---

## 4. Control placement

For every control: what, where, who is authoritative, when, what it trusts and rejects, how it fails, how it is observed
and tested.

| Control | ID | Where | Authoritative | When | Trusts | Rejects | Fails | Observed by | Tested by |
|---|---|---|---|---|---|---|---|---|---|
| Eligibility rule | CTL-001 | Policy decision point | HR system, entitlement registry, classification record | Every request, before retrieval | Status, memberships, cases, label, scope | Grade, title, department, claims, request fields | No decision → no retrieval | Decision in the audit record | TST-ELG-003, TST-ELG-006 |
| Verified identity | CTL-002 | Edge | Identity provider | Every request | Signed token | Unsigned, expired or foreign tokens; asserted identities | Refuse; no downstream call | Edge refusal count | TST-SEC-001 |
| Per-request entitlements | CTL-003 | Policy decision point | HR system, entitlement registry | Every request | Registry and HR responses with versions | Token group claims, request values, question text | Unresolvable → CTL-004 | Registry version in the audit record | TST-SEC-002, TST-CHG-001 |
| Fail closed on unresolved entitlements | CTL-004 | Policy decision point | — | When a source is unavailable or has no record | — | Empty-as-permissive; any degraded mode | No retrieval of any label; safe uniform failure; content-free audit event | Fail-closed events | TST-SEC-005, TST-SEC-006 |
| Only the gateway can search | CTL-005 | Invocation permissions on both tiers | Platform configuration | Always | The gateway's identity | Any other principal | Denied | Denied-access events | TST-SEC-004 |
| Labels from the classification record | CTL-006 | Ingestion | Records system | Every document version | Classification record | Labels in text, file names, folders | Record unreadable → document excluded | Ingestion report | TST-DATA-003 |
| Quarantine invalid classification | CTL-007 | Ingestion | Taxonomy | Every document and section | Valid label and scope pairs | Missing, unknown or mismatched labels | Excluded and reported | Quarantine report | TST-DATA-001, TST-DATA-002 |
| Section-bounded chunking and effective label | CTL-008 | Ingestion | Classification record | Every document version | Section marks | Chunks spanning sections; labels less strict than the document | Section without a valid effective label → excluded | Chunk provenance | TST-ELG-004, TST-DATA-005 |
| Special-category exclusion | CTL-009 | Ingestion, before chunking or embedding | Records-system marks | Every document version | Marks | — | Mark present → section never indexed | Exclusion count | TST-DATA-004 |
| Tier routing | CTL-010 | Ingestion | Effective label | Every chunk | Label | RESTRICTED to the shared tier | Unknown label → excluded | Tier inventory | TST-DATA-006 |
| Shared-tier eligibility constraint | CTL-011 | Gateway → shared search | Decision | Every request | Decision | Question-derived constraints | Cannot build → no call | Constraint hash in audit | TST-ELG-003, TST-ELG-005 |
| Restricted-tier case constraint | CTL-012 | Gateway → restricted search | Decision | Requests with case assignments | Decision | Queries without assignments | No assignments → tier not called | Tier-call record | TST-ELG-006, TST-ELG-007 |
| Complete constraint or nothing | CTL-013 | Gateway | Decision | Every request | Decision | Truncated or question-influenced constraints | Too large or incomplete → refuse | Refusal reason | TST-SEC-003, TST-SCALE-001 |
| Pre-generation verification | CTL-014 | Between search and generation | Current classification record, decision | Every retrieved chunk | Record version | Chunk metadata as final | Any mismatch → withhold all, security event | Security events | TST-SEC-007, TST-CHG-002 |
| Citations from verified chunks | CTL-015 | Response builder | Verification result | Every answer | Verified chunks | Unverified or withheld references | Omit citation | Response record | TST-ELG-003 |
| Uniform "cannot answer" | CTL-016 | Response builder | — | No eligible content, or withheld | — | Existence hints | Uniform message | Response shape comparison | TST-ELG-008 |
| No caching of sensitive answers | CTL-017 | Answer handling | Labels used | Every answer | Labels | Caching CONFIDENTIAL or RESTRICTED | Not cached | Cache inventory | TST-DATA-006 |
| Content-free audit record | CTL-018 | Audit | Audit schema | Every request | Identifiers, versions, labels, scopes, outcomes | Content, excerpts, answers, question text | Missing field → record marked incomplete | Audit review | TST-OBS-001 |
| Content-free operational logging | CTL-019 | All components | Logging configuration | Always | Structured events | Bodies, prompts, completions | — | Log scan for canaries | TST-OBS-001 |
| Decision reconstruction | CTL-020 | Audit | Record versions | On investigation | Stored versions | — | Version missing → reconstruction flagged incomplete | Reconstruction output | TST-OBS-002 |
