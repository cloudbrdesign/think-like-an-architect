# Platform Verification — Kestrelmoor Knowledge Assistant

**Stage:** implementation design · **Date:** 2026-09-15 · **Region:** US East (N. Virginia), `us-east-1`

**Goal:** verify that the platform can implement the approved architecture — **not** change the architecture to suit the
platform.

**Spike discipline:**
- **Scope:** a spike runs only when it changes an implementation decision;
- **Data and isolation:** synthetic data, isolated, reproducible;
- **Cost:** bounded;
- **Cleanup:** destroyed the same day, with the cleanup verified.

**Spike evidence is not validation evidence.** It shows what the platform does at spike scale. The build re-verifies
every relied-upon capability through the named validation tests.

---

## 1. Spike plan

| Spike | Question | Why it matters | Needed? | Status |
|---|---|---|---|---|
| **SPK-E02-A** | Can the managed retrieval service evaluate the eligibility constraints this design needs — expressiveness, grant-set size, section attributes, returned metadata, empty and fail-open behaviour? | The authorization boundary (CTL-011–013) and verification (CTL-014) depend on it; documentation states no filter-size limit | **Yes** | **Run 2026-09-15 · PASS · cleaned up** |
| Identity claim shape, groups and edge-only invocation | Already verified in Episode 01 (VE-05, VE-07, VE-08, VE-17; CH-12). Episode 02 uses `sub` only | — | No — reuse | Re-verified by TST-SEC-001, TST-SEC-004 |
| `Retrieve` authorization is per knowledge base, with no filter-based condition keys | Verified in Episode 01 (VE-01, PE-01); it decides that tiers must be separate knowledge bases, not data sources in one | — | No — reuse | Re-verified by TST-SEC-004 |
| In-Region embedding and generation models | Verified in Episode 01 (VE-06) | — | No — reuse | Preflight |
| Direct ingestion permissions and serial ingestion per knowledge base | Verified in Episode 01 (VE-02, VE-14, CH-07–CH-11) | — | No — reuse | Build |
| Model invocation logging state | Read-only account check | — | No spike: read-only | **No configuration present (2026-09-15)**; checked again in preflight |

**Before SPK-E02-A** (the recorded plan):
- **Created:** one S3 bucket; one S3 Vectors bucket and index; one bounded knowledge-base service role; one knowledge base
  on S3 Vectors; one custom data source.
- **Data:** 12 synthetic sections, 8,203 characters.
- **Estimated cost:** well under USD 0.10.
- **Cleanup:** empty the bucket → delete the stack → verify that no stack, knowledge base, vector bucket or bucket
  remains.

---

## 2. SPK-E02-A results

**Run and scale:**
- **Run:** CloudFormation create 48 s; 12 sections `INDEXED` in 21 s; 42 `Retrieve` calls; total about 4 minutes.
- **Cleanup:** stack `DELETE_COMPLETE`, then verified by the runner and again with independent read-only listing: no
  stack, knowledge base, vector bucket, bucket or spike role remains.
- **Cost:** not yet visible in billing (billing data lags). By volume, well under USD 0.10.

**Format:** each check below records question, assumption, experiment, result, architectural and implementation
consequence.

### C1 — Section attributes survive service chunking
- **Question:** if a section is ingested as one custom document, does every chunk keep the section's attributes?
- **Why it matters:** DATA-003 requires that a chunk never spans sections and never loses its label.
- **Assumption:** the service may split long documents, but attributes are per document.
- **Experiment:** one INTERNAL section of about 7,000 characters, with head and tail markers.
- **Result:** **VERIFIED.** 5 chunks, all carrying `label`, `scope`, `section_id`, `record_version`, `document_id`;
  location type `CUSTOM`. Service keys also returned: `x-amz-bedrock-kb-chunk-id`, `-data-source-id`,
  `-source-file-modality`.
- **Architectural consequence:** none (the design holds).
- **Implementation consequence:** ingest **one custom document per section**, so chunks cannot span sections by
  construction. Service keys are never trusted for authorization.

### C2 — The protected sections are genuinely retrievable (non-vacuity)
- **Result:** **VERIFIED.** Without a constraint, each topic question returned its protected target — pricing (D03 §4),
  finance (D08), controller (D07), incident witness statements (D04 §2), HR case (D05) — mixed with other labels and the
  unlabelled chunk.
- **Consequence:** negative tests on this corpus are meaningful. The harness keeps a precondition run for every negative
  test.

### C3 — The eligibility constraint returns only eligible sections
- **Question:** does `orAll(equals label INTERNAL, andAll(equals label CONFIDENTIAL, in scope grants))` return only
  eligible sections across all questions?
- **Experiment:** three personas (no grants; BID-ORION; FIN-REPORTING) × 6 questions.
- **Result:** **VERIFIED.** Zero ineligible results in 18 queries; every query returned results; BID-ORION retrieved
  D03 §4, and FIN-REPORTING retrieved D08.
- **Implementation consequence:**
  - `orAll` and `andAll` need at least two members (API reference), so a person with no domains gets the single
    `equals label INTERNAL` shape;
  - a one-element `in` list works.

### C6 — Constraint size for large grant sets (NFR-002)
- **Question:** up to what grant count is the constraint accepted and evaluated completely? The only relevant domain is
  placed **last**, so truncation would show.
- **Result:**

| Grants | Constraint bytes | Accepted | Relevant domain retrieved | Ineligible results |
|---|---|---|---|---|
| 40 | 926 | yes | yes | 0 |
| 100 | 2,066 | yes | yes | 0 |
| 250 | 4,916 | yes | yes | 0 |
| 500 | 9,666 | yes | yes | 0 |
| 1,000 | 19,166 | **no** — `ValidationException`: "The requested filter exceeds the maximum allowable size of 15360 bytes." | — | — |
| 2,000 / 5,000 | 38,166 / 95,166 | no (same error) | — | — |

- **Architectural consequence:** none. NFR-002 (about 40 grants) uses 6% of the limit, and the service **rejects** an
  over-size filter instead of truncating it (fail closed).
- **Implementation consequence:** the gateway checks the serialised size against an explicit budget below the lowest observed limit **before** calling and
  refuses above it (`REFUSED_CONSTRAINT_INCOMPLETE`). TST-SCALE-001 includes an over-limit persona. RR-10 records the
  measured limit.

### C7 — Case constraint inside a tier holding several cases
- **Result:** **VERIFIED.** `andAll(equals label RESTRICTED, in scope [SI-0417])` returned only SI-0417 (for the
  incident and the HR question alike); `[HR-2031]` returned only HR-2031.
- **Architectural consequence:** confirms the D3 clarification — the constraint, not the tier, separates cases
  (TST-ELG-009).

### C8 — Nothing eligible, and relevance
- **Result:**
  - a constraint no chunk satisfies returns **0 results with no error**;
  - an unrelated question under the INTERNAL constraint still returns INTERNAL chunks (scores about 0.48–0.50).
- **Implementation consequence:**
  - an empty result means "nothing eligible" and returns the uniform response;
  - relevance is **not** a filter, so the response builder applies a relevance threshold to verified chunks before
    generation (answer quality only).

### C9 — Negative operators fail open
- **Result:** **VERIFIED (a risk).** `notEquals label RESTRICTED` and `notIn label [RESTRICTED, CONFIDENTIAL]` both
  returned the **unlabelled** chunk: a chunk without the attribute matches a negative condition, as the API reference
  describes for `notEquals`.
- **Architectural consequence:** reinforces DATA-005 (an unlabelled chunk must never be indexed).
- **Implementation consequence:** the constraint builder uses positive operators only; an L0 unit test forbids
  `notEquals` and `notIn`.

### C10 — Label values match exactly
- **Result:** `equals label INTERNAL` did **not** match a chunk labelled `internal`; `equals label internal` did.
- **Implementation consequence:** ingestion rejects non-canonical labels (quarantine) and never normalises them. The
  corpus gains fixture D-15 (lower-case label) for TST-DATA-002.

### C11 — The constraint limits candidates during search
- **Result:** **VERIFIED.** With enough eligible chunks, a constrained query returned the full 5 of 5 requested, which is
  consistent with S3 Vectors documentation (filter evaluated during the search, not after it).
- **Consequence:** the retrieval-layer observation in every eligibility test reflects the boundary itself.

---

## 3. Platform capability decision record

| ID | Capability | Evidence | Decision | Re-verified at build by |
|---|---|---|---|---|
| PCD-01 | Search-time constraints with `orAll` / `andAll` / `equals` / `in` on a knowledge base backed by S3 Vectors | SPK-E02-A C3, C7, C11; S3 Vectors metadata filtering documentation | **Use** as the enforcement mechanism for CTL-011, CTL-012 | TST-ELG-001–009, TST-SEN-001 |
| PCD-02 | Negative operators match chunks lacking the attribute | C9; API reference for `notEquals` | **Prohibit** negative operators in constraints | L0 unit test; TST-DATA-001 |
| PCD-03 | Filter size limits: 15,360 bytes at the retrieval API (spike) and 10,240 bytes at the vector store (build re-measurement); over-size requests rejected, not truncated | C6 | **Pre-check and refuse**; NFR-002 margin confirmed | TST-SCALE-001 |
| PCD-04 | `Retrieve` is authorised per knowledge base; no filter-based condition keys; no documented resource policy for customer-managed knowledge bases | Episode 01 VE-01, PE-01, CH-02 | **Two knowledge bases** (one per tier), each with its own vector bucket and index, section bucket and service role; exclusivity through the query role only | TST-SEC-004 |
| PCD-05 | Direct ingestion to a custom data source with inline attributes; attributes preserved on every chunk | C1; Episode 01 VE-03, VE-14 | **One custom document per section** | TST-DATA-005 |
| PCD-06 | Exact, case-sensitive attribute matching | C10 | **Reject non-canonical labels** at ingestion | TST-DATA-002 |
| PCD-07 | Results return custom attributes and chunk IDs | C1; Episode 01 SPK-E | **Verification** uses `document_id`, `section_id`, `record_version`, `label`, `scope` against the classification store | TST-SEC-007, TST-CHG-002 |
| PCD-08 | Retrieve and generate as separate steps | Design (generation must follow verification) | **Use `Retrieve` + `Converse`**; application-built citations; the combined retrieve-and-generate operation is not used | TST-ELG-001 |
| PCD-09 | Empty results when nothing is eligible; relevance is not a filter | C8 | **Uniform response** on empty; relevance threshold on verified chunks | TST-ELG-008 |
| PCD-10 | Model invocation logging off; no prompt caching used | Read-only account check 2026-09-15; request design | **Preflight check**; no cache checkpoint | TST-OBS-001; L0 test |
| PCD-11 | CloudFormation creates and deletes the retrieval-tier resources cleanly | SPK-E02-A deploy and cleanup; Episode 01 VE-12 | Input to the mechanism recommendation | TST-OPS-001 |

## 4. Platform behaviours that could undermine requirements, and how the design neutralises them

| Platform behaviour | Requirement | Neutralised by |
| --- | --- | --- |
| Any principal with `bedrock:Retrieve` on a knowledge base can query it unfiltered | SEC-001, SEC-004 | CTL-005: only the query role holds `Retrieve`; TST-SEC-004 |
| Negative operators include chunks without the attribute (C9) | SEC-001, SEC-004 | PCD-02 positive operators only; DATA-005 quarantine |
| Group claims reach the function as strings and can be stale until token expiry (Episode 01 CH-12; ASM-008) | SEC-003 | CTL-003 ignores claims; TST-SEN-003 shows why |
| Over-size filter → service error (C6); empty result is not an error (C8) | SEC-007 | Error and over-size → refuse; empty → uniform response, never "no restriction" |
| Chunk attributes are copies set at ingestion; an index cannot know about a later reclassification | SEC-008 | CTL-014 compares with the current classification record |
| The service indexes whatever text it receives, including text that claims its own classification | DATA-002 | Attributes come only from the classification store; D-14 test (C3 showed the text claim had no effect) |
| The service splits long documents into several chunks | DATA-003 | One document per section; attributes on every chunk (C1) |
| Anything ingested is embedded and stored as vector metadata text | DATA-004 | CTL-009 removes special-category sections before any ingestion call |

## 5. Platform limitations discovered

- **Filter size:** 15,360 bytes at the retrieval API (spike) and 10,240 bytes at the vector store (build re-measurement, §6), both measured; the documentation read stated neither.
- **Negative operators fail open** for missing attributes (measured; documented for `notEquals`).
- **Label matching is exact.**
- **Relevance does not filter:** eligible but unrelated chunks are returned.
- **Logical operator arity:** `orAll` and `andAll` require at least two members (documented).
- **Custom metadata on S3 Vectors-backed knowledge bases:** up to 1 KB and 35 keys per vector (documented). The design
  uses 5 short keys.

---

## 6. Build re-measurement — a second, lower limit (2026-09-15)

**Status:** validation evidence from the build, recorded separately from the spike evidence above.

**What happened:** TST-SCALE-001 re-measured the constraint size near the spike's figure. Filters between about 10,300
and 15,360 bytes were rejected by a different layer: `Filter must have at most 10240 bytes (Service: S3Vectors)`.
The spike had tested 500 grants (accepted) and 1,000 grants (rejected by the retrieval API at 15,360 bytes), so it
never reached the vector store's own limit.

**Bisection** (operator credentials, shared tier, FIN-REPORTING always the last grant):

| Identifier length | Largest accepted | Smallest rejected | Rejected by |
|---|---|---|---|
| Short (`SYN-PROBE-0000`) | 561 grants · 10,265 bytes (as the builder measures) | 562 grants · 10,283 bytes | Vector store, 10,240-byte limit |
| Long (`SYN-LONGER-PROBE-IDENTIFIER-0000`) | 281 grants · 10,265 bytes | 282 grants · 10,301 bytes | Vector store, 10,240-byte limit |

Every accepted constraint returned the last grant's section: no truncation was observed.

**Consequences:**
- **Architectural:** none. Filtering during search still enforces the model; an over-size constraint is rejected, not
  truncated. NFR-002 (about 40 grants, 926 bytes) uses about 9 % of the lower limit.
- **Implementation:** the application budget is lowered from 12,288 bytes (80 % of the spike's figure) to **8,192
  bytes** (80 % of the lower limit), measured with the builder's own serialisation, which tracked the vector store's
  count within 25 bytes for both identifier lengths.
- **Validation:** TST-SCALE-001 now also checks, on the deployed service, that the largest constraint the application
  accepts is accepted with its last grant honoured, and that a constraint above the observed limit is rejected.
- **Record:** RR-10 updated. Both limits are observed platform behaviour under the tested conditions, not architectural
  constants.

**Evidence:** `07-evidence/implementation-validation-2026-09-15/filter-limit-measurement/filter-size-measurement.json`.

