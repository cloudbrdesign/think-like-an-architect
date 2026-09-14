<!-- template: tla-adr/1 -->
# ADR-004 — Document tenant attribution: assigned once by the ingestion service, cross-checked, immutable

**Status:** accepted — architecture approved 2026-09-14 · **Date:** 2026-09-14
**Answers:** decision question DQ-D · **Options analysis:** [section 5](ARCHITECTURE_OPTIONS_ANALYSIS.md#5-document-tenant-attribution--adr-004)

## Context

The retrieval boundary (ADR-005) enforces **attribution, not truth**. A perfect tenant constraint still serves a document
to whichever tenant it is attributed to. Attribution is therefore the boundary's weakest input: it must be assigned by a
trusted component, from verified identity, exactly once, and it must be impossible to change quietly. In the pilot,
documents enter only through the platform's authenticated upload feature (ASM-006).

## Requirements driving this decision

- **SEC-006** (invariant) — exactly one owning tenant, assigned at ingestion by a trusted component from the uploader's
  verified tenant; never from document content or an uploader-chosen value.
- **SEC-007** — attribution cannot change through any user-facing path; corrections are authorised and recorded.
- **DATA-001** — owner, uploader, ingestion time and processing status are recorded for every document.
- **DATA-002** — derived data inherits the owner.
- **DATA-003** — mis-attribution can be detected or corrected, and its consequence is stated.
- **FUN-002**, **FUN-003**, **BUS-001** — uploads become available; deletion stops retrieval; disabled tenants are not
  processed.
- **SEC-008** (invariant) — missing or invalid attribution fails closed.
- Assumptions: ASM-005, ASM-006, ASM-008.

## Options considered

| Option | Source of ownership | Verdict |
|---|---|---|
| A — Uploader chooses | Form field or supplied metadata | Fails SEC-006 |
| B — Storage location only | Folder or key prefix | Useful cross-check; a location is not a record, and anything that can write there creates ownership |
| **C — Ingestion service assigns from verified tenant context** | Trusted service → ownership record → indexing attribute | Chosen, cross-checked against B |
| D — Document content | Labels or names inside the document | Content is untrusted input |
| E — Editable by administrators in the product | User-facing update | Fails SEC-007 |

## Trade-offs

A single authoritative assignment makes ownership provable, but it cannot know whether the uploaded **content** truly
belongs to the uploader's company. Content inspection could flag some mistakes, but it would make ownership depend on
untrusted text. The decision accepts that a consistent-but-wrong upload is a residual risk, and makes it **investigable
and correctable** rather than pretending it can be prevented.

## Decision

1. **One entry path.** Documents enter only through the upload route: API edge verification → Tenant Context Resolver →
   ingestion service. Clients never write to document storage or the retrieval structure directly.
2. **Refuse chosen ownership.** The upload request accepts only the documented fields; a request that tries to set an
   owner, tenant or document identifier is **refused** and recorded (`REQUEST_FIELD_REJECTED`).
3. **Server-generated identity.** The ingestion service generates the document identifier and derives the storage
   location from the tenant context: `tenants/<tenant_id>/documents/<document_id>`.
4. **Ownership record first.** It writes the authoritative ownership record — `document_id`, owning tenant, uploader user
   identifier, ingestion time, status `RECEIVED` — before indexing begins (CTL-011).
5. **Consistency gate.** Before indexing, the owner in the ownership record, the tenant segment of the storage location
   and the owner value about to be passed to indexing must be identical, well formed, and belong to an ENABLED tenant.
   If any is missing, malformed or different, the document is **QUARANTINED**: not indexed, retrievable by no one, and a
   security event is recorded (CTL-012).
6. **The service supplies the owning-tenant attribute to indexing.** The ingestion service passes the owner and the
   document identifier as indexing attributes itself. Ownership never comes from a file that the uploader, the document
   or another component could edit (CTL-011, CTL-001).
7. **Content is never ownership.** Labels, headers or names inside a document ("Confidential — Tenant B") are content.
   They do not influence attribution.
8. **Immutable attribution.** No operation changes a document's owner. A correction is an **operator workflow**:
   quarantine → remove from the index → delete → re-ingest as a **new** document under the correct tenant, with every
   step recorded (CTL-013, CTL-010).
9. **Exclusive indexing permission.** Only the ingestion service may add documents to, or remove them from, the retrieval
   structure (CTL-013).
10. **Deletion by the owning tenant only.** The delete route resolves the document through the ownership record; a
    document of another tenant behaves as **not found** (no existence disclosure). Status moves `DELETING` → removed
    from index → original deleted → `DELETED`. Because retrieval verification discards results whose status is not
    `AVAILABLE` (CTL-017), a deleting document stops appearing in answers immediately, even while storage-level removal
    completes within the agreed window (ASM-008) (CTL-014).
11. **Disabled tenants** cannot upload (resolver denies) and are not served (ADR-002).

### The mislabelled-document threat — expected outcomes (fixed before TST-ASM-010 runs)

| Case | Example | Architecture outcome |
|---|---|---|
| (a) **Inconsistent attribution** | Ownership record says A, but the location or indexing value says B; or the owner value is missing or malformed | **PREVENTED AND QUARANTINED** by the consistency gate (CTL-012). Retrievable by no one. Security event recorded |
| (b) **Consistent but wrong** | A Tenant A user uploads a file that actually contains Tenant B's information (a consultant picks the wrong file) | **EXPOSED AS A RESIDUAL RISK** (RR-03). The document is Tenant A's by attribution and is served only to Tenant A. The boundary enforces attribution, not truth. **Detection and correction:** the ownership record shows who uploaded it and when; security audit records show every retrieval of it and by whom; the operator correction workflow removes it |
| (c) **Index attribute diverges from the ownership record** | A path outside the ingestion service wrote a chunk with owner B for a document recorded as A's | **DETECTED** at retrieval by ownership verification (CTL-017): the whole response is withheld and a security event recorded (TST-SEC-022) |

## Why not the other options

- **Why not let the uploader choose (A)?** SEC-006 forbids it, and it recreates the legacy endpoint's flaw on the write
  path.
- **Why not storage location alone (B)?** A location is a naming convention. Any component or person able to write to a
  location would create ownership, and nothing would record who assigned it. It is kept only as a cross-check.
- **Why not derive ownership from content (D)?** A hostile or mistaken document could claim to belong to anyone.
- **Why not editable ownership (E)?** Mutable ownership is an isolation bypass (SEC-007): changing a document's owner
  moves it across the boundary without anyone retrieving anything illegitimately.

## Consequences

**Positive**
- Ownership is provable: one authoritative record, one assigning component, a recorded history.
- Divergence between the record and the index is detectable on every retrieval.
- Quarantine turns attribution errors into a visible state instead of a silent leak.

**Negative / accepted trade-offs**
- Corrections are slower (re-ingest) than an edit. Accepted: speed of correction is less important than preventing
  silent reassignment.
- The ingestion service and its indexing permission become security-critical.
- Consistent-but-wrong uploads cannot be prevented technically (RR-03). Content classification is Episode 02.
- A very large upload batch from one tenant can delay indexing for others (ADR-001, RR-13).

## Residual risks

RR-03 consistent-but-wrong attribution · RR-06 permission drift · RR-09 deletion window · RR-13 ingestion contention.

## Controls introduced

| ID | Control | Enforcement point |
|---|---|---|
| CTL-011 | **Server-side attribution.** The ingestion service generates the document identifier, derives the storage location from tenant context, writes the ownership record (owner, uploader, time, status) and itself supplies the owning-tenant and document identifier attributes to indexing; request fields that try to set ownership are refused | Ingestion service |
| CTL-012 | **Attribution consistency gate and quarantine.** Record owner = location tenant = indexing owner, well formed, tenant ENABLED — otherwise QUARANTINED, not indexed, security event | Ingestion service, before indexing |
| CTL-013 | **Immutable attribution and exclusive indexing permission.** No operation updates an owner; corrections are the recorded operator workflow; only the ingestion service may add or remove indexed documents | Ingestion service; permission policies on the retrieval structure; operator runbook |
| CTL-014 | **Ownership-checked document operations.** Opening (citation links) and deleting a document resolve it through the ownership record and the caller's tenant context; another tenant's document behaves as not found; deletion moves status `DELETING` → `DELETED` and removes the index entry and original | Ingestion service (document routes) |

## Validation implications

- TST-SEC-019 tries to choose the owner through request fields and embedded values.
- TST-SEC-020 tries to change ownership through every user-facing path; TST-SEC-023 checks indexing permission
  exclusivity.
- TST-ASM-010 runs cases (a) and (b) with the outcomes above; TST-SEC-022 runs case (c).
- TST-DATA-014 deletes a document and asks about it; TST-DATA-016 attempts upload and retrieval for a disabled tenant.

## Platform evidence (checked after the decision)

- The implementation environment offers two ways to supply indexing attributes. **(1)** A metadata file stored next to
  each document in object storage (PC-08). **(2)** Direct ingestion into a custom data source, with attributes supplied
  inline by the caller (PC-07). Option (1) would make ownership a separately writable object beside the document — a
  second, editable source of truth. The mapping therefore uses **(2)**: the ingestion service supplies the owner in the
  same call that indexes the document. This refines **how** CTL-011 is implemented; the decision is unchanged.
- Service-reserved metadata fields cannot be overwritten (PC-03). Indexing and ingestion quotas (PC-06) inform RR-13.

## Related

- Requirements: SEC-006, SEC-007, SEC-008, DATA-001, DATA-002, DATA-003, FUN-002, FUN-003, BUS-001
- Decisions: ADR-001, ADR-002, ADR-003, ADR-005
- Tests: TST-SEC-019, TST-SEC-020, TST-ASM-010, TST-SEC-022, TST-SEC-023, TST-DATA-014, TST-DATA-016
