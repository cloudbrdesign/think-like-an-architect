# Educational Implementation Design — Kestrelmoor Knowledge Assistant

**Stage:** implementation design, as built · **Status:** design accepted; implementation built 2026-09-15 (§14) · **Date:** 2026-09-15

**What this is:** the design of the free educational implementation of the approved architecture (ADR-001 … ADR-006).

**What was built:** the source in `app/`, `infrastructure/`, `scripts/` and `../06-validation/harness/`. Platform assumptions were
checked by the verification spike and re-measured during the build ([PLATFORM_VERIFICATION.md](PLATFORM_VERIFICATION.md)). §14
lists every difference between this design and the implementation.

**Rule of the design:**
- **Local:** logic that can be shown clearly without a cloud runs locally and in public CI.
- **AWS:** claims about managed retrieval, tier permissions and service configuration are verified only against AWS,
  never simulated and then reported as verified.

---

## 1. What the learner will build

A small internal knowledge assistant for Kestrelmoor, in three pieces:
1. **Local core** (no AWS, no cost) — plain Python modules with unit tests:
   - the eligibility rule;
   - classification validation;
   - section processing with effective labels;
   - constraint construction (positive operators only, size-checked);
   - pre-generation verification logic;
   - the content-free audit record;
   - the canary oracle.
2. **AWS deployment** (billable, cleaned up in the same session) — the same modules running behind a verified identity
   edge, with two retrieval tiers, the authoritative grants and classification stores, and a content-free audit store.
3. **Validation harness** — the 31 tests, the canary scanner, the three failure experiments and evidence bundles.

## 2. Implementation mechanism (recommendation)

**Decision question:** which mechanism makes the taught controls most visible and testable, while staying reproducible,
destroyable and cheap? The controls in question are the eligibility decision, tier permissions, label propagation, the
constraint, verification and fail-closed behaviour.

**Episode 02's specific needs:**
- **Four deployments:** the normal system plus three failure variants, each destroyed after use.
- **Visible permissions:** two tiers whose permissions must be readable side by side.
- **Stores and roles:** a grants store, a classification store and an audit store with distinct read and write rights.

| Option | Visibility of the taught controls | Four isolated deployments | Destroy and verify | Learner tooling | Verdict |
|---|---|---|---|---|---|
| **A — One CloudFormation template (with a `Variant` parameter) + small Python ops scripts + Python application and harness** | Every tier role, bucket policy and table permission in one readable file; controls in named Python modules | One stack per deployment name; variants differ only by the packaged module the parameter selects | Stack deletion plus a verified cleanup check; a variant's destruction is observable as a stack status | AWS CLI and Python (already needed) | **Recommended** |
| B — Terraform + Python | Equally readable | A workspace or state per deployment | `terraform destroy` per state | Terraform, state handling, provider versions | Not recommended: four state lifecycles add machinery that teaches nothing about eligibility. Resource support for knowledge bases on S3 Vectors was **not verified** for Terraform at this gate |
| C — AWS CDK | Permissions generated behind constructs | Stacks per variant | `cdk destroy` | Node.js + CDK | Not recommended: hides the tier permission boundary that learners must read |
| D — AWS SAM | Readable template | Stacks per variant | Leaves an artifact stack | SAM CLI | Not recommended: extra side resources for learners to forget |
| E — CLI / SDK scripts only | API calls visible; permissions scattered | Hand-rolled state per deployment | Error-prone ordered teardown | CLI | Not recommended |

**Why A — reasons specific to this episode:**
- **One file answers the key question:** "who can query the restricted tier, who can write the grants store?"
  (TST-SEC-004 checks the deployment against it).
- **Clean variants:** the three variants are the same template with a different, test-only module, so a learner can see
  exactly one thing change.
- **Verified resource support:**
  - the retrieval-tier resource types (vector bucket, index, knowledge base on S3 Vectors, custom data source) were
    created and deleted by a template in the Episode 01 verification (VE-12);
  - they were created and deleted again today by SPK-E02-A (created in 48 s; deletion verified).

**Not chosen because Episode 01 used it:** Episode 01's use is not the reason. The reasons above would stand for a new
episode.

**Decision:** option A, CloudFormation + Python (accepted).

## 3. Components

| Component | Where it runs | Implements | Why it must be there |
|---|---|---|---|
| Local core modules (`app/core/`) | Laptop, public CI and inside both functions | CTL-001, CTL-007, CTL-008 (logic), CTL-013 (builder), CTL-014 (comparison), CTL-018 (schema) | Pure logic; testable without cost; the same code is deployed, so local tests exercise the deployed rules |
| Identity: Amazon Cognito user pool | AWS | Verified identity tokens for synthetic personas | SEC-002 needs a real identity provider issuing signed tokens |
| Edge: Amazon API Gateway HTTP API with a JWT authorizer | AWS | CTL-002 | Token verification before any application code runs |
| Query function (AWS Lambda) | AWS | Policy decision point (CTL-001, CTL-003, CTL-004), retrieval gateway (CTL-011–013), verification (CTL-014), response builder (CTL-015–017), generation call, audit write (CTL-018) | Separate modules in one function (teaching simplification TS-E02-01) |
| Ingestion function (AWS Lambda) | AWS | CTL-006, CTL-007, CTL-008, CTL-009, CTL-010 | Ingestion is a trusted component; it runs with its own role, not the learner's |
| Grants store: Amazon DynamoDB table `…-authorization` | AWS | Authoritative employment status (HR record type) and entitlements (registry record type), each versioned | SEC-003: authoritative grants read per request; its unavailability must be observable (TST-SEC-005) |
| Classification store: DynamoDB table `…-classification` | AWS | Authoritative document and section labels, scopes, special-category marks, record versions | DATA-002, SEC-008: the current record that verification compares against |
| Audit store: DynamoDB table `…-audit` | AWS | Content-free decision records | SEC-012, OPS-002; deterministic lookup by request (Episode 01 CH-05) |
| Records bucket: Amazon S3 | AWS | Synthetic source documents (the simulated records system) | Ingestion reads from a source it does not control |
| Shared-tier section bucket and restricted-tier section bucket: Amazon S3 | AWS | One object per section, written only by ingestion | Storage-level separation of tiers; each tier's knowledge-base role reads only its own bucket |
| Shared-tier and restricted-tier retrieval: two Amazon Bedrock knowledge bases, each with a custom data source and its own Amazon S3 Vectors bucket and index | AWS | Search-time evaluation of the constraint (CTL-011, CTL-012) | The claims "evaluated during search" and "tiers separately permissioned" require the real managed service (SPK-E02-A) |
| Embeddings: Amazon Titan Text Embeddings V2 (In-Region) | AWS | Vectors for sections and questions | Required by the knowledge bases |
| Generation: Amazon Nova Micro (In-Region, Converse) | AWS | Answers from verified chunks only | Generation must follow verification; In-Region model IDs verified in Episode 01 (VE-06) |
| Amazon CloudWatch Logs | AWS | Function and API access logs, 1-day retention, content-free | Operational troubleshooting without content (CTL-019) |
| IAM roles (runtime boundary) | AWS | CTL-005 and least privilege per component | The permission boundary is part of the lesson |
| Validation harness (`06-validation/harness/`) | Laptop | 31 tests, canary scanner, three experiments, evidence bundles | Observes the deployment from outside, like a reviewer |

**Deliberately not used:**
- **Retrieve-and-generate in one call:** generation must happen only after verification, and citations are built from
  verified chunks.
- **API response caching, prompt caching, model invocation logging, CloudTrail data events.**
- **OpenSearch, customer-managed KMS keys, VPCs.** None is needed for the taught controls, and none is billed by the hour.

## 4. Trust boundaries (implementation)

| # | Boundary | What crosses | What is enforced there |
|---|---|---|---|
| B1 | Client → API edge | Question + access token | Token signature, issuer, audience, expiry (CTL-002); nothing else from the client is an authorization input |
| B2 | Edge → query function | Verified claims (`sub` only is used) | Function accepts only the authorizer context; the Lambda resource policy admits only this API (Episode 01 VE-07, VE-17) |
| B3 | Query function → grants store | Employee ID → status, memberships, cases, versions | Read-only role; any error → no retrieval (CTL-004) |
| B4 | Query function → retrieval tiers | Question + constraint | Only this role may call `Retrieve` on either knowledge base (CTL-005); constraint built only from the decision |
| B5 | Knowledge-base roles → section buckets and vector indexes | Section objects, vectors | Shared-tier role reads only the shared bucket and index; restricted-tier role only the restricted ones |
| B6 | Query function → classification store | Chunk identifiers → current records | Read-only; unavailable → withhold (CTL-014) |
| B7 | Query function → generation | Verified chunks + fixed instructions | Only after verification PASS |
| B8 | Ingestion function ← records bucket and classification store | Source documents, records | Labels only from the store; special-category removed before any service call |
| B9 | Ingestion function → section buckets and knowledge bases | Section objects + inline attributes | Only ingestion may write section buckets and ingest documents |
| B10 | All components → audit and logs | Identifiers, versions, decisions | No content, excerpts, answers or questions |
| B11 | Learner / harness (administrative path) | Fixture loading, inventories, fault injection | Teaching simplification TS-E02-03: the sandbox administrator is operator and tester |

## 5. Flows

### 5.1 Identity flow
1. The harness signs in a persona (administrator-initiated auth flow, TS-E02-04), and Cognito returns an access token.
2. The HTTP API JWT authorizer verifies it. An invalid or missing token gets 401, and the function is never invoked.
3. The query function reads only `sub` from the authorizer context and maps it to the synthetic employee ID.
   `cognito:groups` is ignored in the normal build; only the TST-SEN-003 variant reads it.

### 5.2 Authorization flow (policy decision point)
1. `GetItem` status record and `Query` grant records for the employee, with consistent read, from the grants store.
2. **No record, INACTIVE, or any error or timeout** → decision `UNAVAILABLE` or `DENIED`, no retrieval, uniform failure,
   audit `REFUSED_AUTHORIZATION_UNAVAILABLE` or `REFUSED_NO_ACTIVE_EMPLOYMENT` (CTL-004).
3. Otherwise the decision is `{active, domains[], cases[], hr_version, grants_version}` (CTL-001).
4. **Nothing cached** at module level across invocations: warm containers must not reuse grants (L0 check and TST-CHG-001).

### 5.3 Classification and ingestion flow
1. **Load (harness):** the fixture loader writes synthetic source documents to the records bucket and classification
   records to the classification store, then invokes ingestion.
2. **Read (ingestion):** for each document, ingestion reads the record — labels are never taken from text.
3. **Validate** (CTL-007):
   - the label is one of `INTERNAL | CONFIDENTIAL | RESTRICTED`, exactly;
   - the scope is present for CONFIDENTIAL and RESTRICTED, and absent for INTERNAL;
   - a failure quarantines the section or document and records it.

   Label matching in the retrieval service is exact (SPK-E02-A C10), so non-canonical labels are rejected, never
   normalised.
4. **Special-category exclusion** (CTL-009): marked sections are dropped here, before any object write or ingestion call.
5. **Section objects** (CTL-008): one object per section, carrying the effective label and scope (never less restrictive
   than the document) plus `document_id`, `section_id` and `record_version`.
   - **Chunking:** the service may split a long section into several chunks, but every chunk keeps the section's
     attributes (SPK-E02-A C1), so a chunk can never span sections.
6. **Routing** (CTL-010): INTERNAL and CONFIDENTIAL objects go to the shared bucket and knowledge base; RESTRICTED
   objects go to the restricted bucket and knowledge base only.
7. **Ingestion call:** direct ingestion with inline attributes, serialised per knowledge base (one concurrent ingestion job
   per knowledge base; Episode 01 VE-02). Ingestion waits for `INDEXED`.

### 5.4 Retrieval flow (gateway)
1. **Shared-tier constraint** (CTL-011):
   - with no domains: `equals(label, INTERNAL)`;
   - otherwise: `orAll(equals(label, INTERNAL), andAll(equals(label, CONFIDENTIAL), in(scope, domains)))`.

   `orAll` needs at least two members, which is why the no-domain case is a distinct shape (SPK-E02-A C3).
2. **Restricted-tier constraint** (CTL-012), only when `cases` is non-empty:
   `andAll(equals(label, RESTRICTED), in(scope, cases))`.
3. **Builder rules** (CTL-013):
   - **Operators:** positive only (`equals`, `in`, `andAll`, `orAll`). `notEquals` and `notIn` match chunks that lack the
     attribute and would fail open (SPK-E02-A C9); an L0 test fails the build if they appear.
   - **Size:** each serialised constraint is checked against an 8,192-byte budget below the service's measured limits (15,360 bytes at the retrieval API, SPK-E02-A C6; 10,240 bytes at the vector store, build re-measurement). An
     over-limit request refuses, and is never truncated. The service rejects over-size filters as well.
   - **Sources:** no input other than the decision reaches the builder; the question is passed only as the query text.
4. **Search:** `Retrieve` on each allowed tier (numberOfResults 5 per tier). Results are merged by score.
   - **An empty result is "nothing eligible"** (SPK-E02-A C8), never "no restriction".

### 5.5 Pre-generation verification flow (CTL-014)
1. **Batch read:** for every retrieved chunk, the classification record for `(document_id, section_id)` is batch-read from
   the classification store.
2. **Compare:** each chunk is compared with its record:
   - the record exists and is not special-category;
   - the chunk's label and scope equal the record's **current** label and scope;
   - the chunk's `record_version` equals the current version, or the change was downward (still stricter, allowed until
     re-index);
   - the current label and scope are eligible under **this request's** decision;
   - the chunk came from the tier that label belongs to.
3. **Any failure, or the store unavailable** → withhold the whole answer, security event `VERIFICATION_MISMATCH` or
   `CLASSIFICATION_UNAVAILABLE`, uniform response.
4. **All pass** → relevance check. If no verified chunk meets the relevance threshold, return the uniform "cannot answer"
   response (FUN-003). The threshold only affects answer quality, never eligibility; it is calibrated during build.

### 5.6 Generation and response
Nova Micro Converse, In-Region model ID, fixed instructions plus verified chunk texts. There is no tool use and no cache
checkpoint.
- **Citations:** built by the response builder from verified chunks only — document title and section title.
- **Uniform response:** one fixed message and HTTP 200 shape for "nothing eligible", "withheld" and "authorization
  unavailable". The audit record distinguishes the three cases; the response does not.

### 5.7 Fail-closed flow (every path that must produce no retrieval or no generation)

| Trigger | Where | Retrieval? | Generation? | User sees | Audit outcome · failing control |
|---|---|---|---|---|---|
| Missing or invalid token | Edge | No | No | 401 | (edge access log only) · CTL-002 |
| Grants store unavailable, error or timeout | Policy decision point | **No** | No | Uniform failure | `REFUSED_AUTHORIZATION_UNAVAILABLE` · CTL-004 |
| No employee record / INACTIVE | Policy decision point | No | No | Uniform failure | `REFUSED_NO_ACTIVE_EMPLOYMENT` · CTL-004 |
| Constraint cannot be built or exceeds size | Gateway | No | No | Uniform failure | `REFUSED_CONSTRAINT_INCOMPLETE` · CTL-013 |
| Retrieval service error | Gateway | Attempted, no result used | No | Uniform failure | `RETRIEVAL_ERROR` · CTL-013 |
| Nothing eligible | Gateway | Yes, empty | No | Uniform "cannot answer" | `NO_ELIGIBLE_CONTENT` |
| Verification mismatch | Verification | Yes | **No** | Uniform "cannot answer" | `WITHHELD_VERIFICATION_MISMATCH` · CTL-014 |
| Classification store unavailable | Verification | Yes | No | Uniform "cannot answer" | `WITHHELD_CLASSIFICATION_UNAVAILABLE` · CTL-014 |
| Model error | Generation | Yes | Attempted | Uniform failure | `GENERATION_ERROR` |
| Invalid label at ingestion | Ingestion | — | — | (not indexed) | Quarantine record · CTL-007 |

## 6. Audit and observability design (CTL-018 – CTL-020)

**One audit item per request.** The partition key is `request_id`, and the audit store is written once per request.

| Field | Purpose |
|---|---|
| `request_id`, `timestamp`, `deployment`, `variant` | Correlation; which deployment produced the record |
| `employee_id` | Who asked (synthetic ID mapped from `sub`) |
| `decision.status` | `ALLOW` · `DENIED` · `UNAVAILABLE` |
| `decision.hr_version`, `decision.grants_version`, `decision.domains`, `decision.cases` | Which authoritative grants were used (identifiers only) |
| `tiers_called` | `shared`, `restricted` or none (proves the tier was or was not queried) |
| `constraints[].tier`, `sha256`, `bytes` | Which eligibility scope was applied, without storing it as a leak surface (IDs only are inside) |
| `retrieval[].chunk_id`, `document_id`, `section_id`, `label`, `scope`, `record_version`, `tier` | What crossed the retrieval boundary — the primary observation point for every eligibility test |
| `verification.status`, `verification.mismatches[].chunk_id`, `reason` | Whether the check passed and why not |
| `generation.invoked`, `model_id`, `input_tokens`, `output_tokens` | Whether generation occurred; usage for cost |
| `outcome`, `failing_control` | Final outcome; which control stopped the request |
| `latency_ms` (per stage) | Performance evidence (NFR-001) |

**Never recorded:**
- document text, chunk text or excerpts;
- answer text;
- the question — neither text nor hash; the harness correlates by `request_id`, so no question-derived value is needed;
- special-category content;
- tokens, credentials or secrets.

**Operational logs:**
- **Content:** structured events with `request_id`, stage, outcome and timings; no bodies. The API access log format
  excludes the request body.
- **Retention:** 1 day.
- **Model logging:** model invocation logging is checked off in preflight — the read-only account check on 2026-09-15
  showed no configuration.

**Reconstruction** (CTL-020):
- **Grants:** the harness re-derives the decision from `hr_version` and `grants_version`. The grants store keeps
  versioned history for the session.
- **Verification:** it re-checks each chunk against the classification record versions.
- **Reports:** quarantine and mismatch reports are generated from the audit and quarantine records.

## 7. Cache analysis

| Possible cache | Could it bypass request-time authorization? | Decision | How it is checked |
|---|---|---|---|
| Application response cache | Yes — a key missing the requester's decision would serve one person's answer to another | **Excluded.** Episode 02 needs no response caching; cost work is Episode 05 | L0: no cache module; L1: template has no cache resources; TST-DATA-006 inventory |
| API response caching at the edge | Yes, the same risk | **Not configured**; HTTP API stage settings contain no caching configuration | L1 template check at build |
| Prompt or model context caching | Yes, if cached context from one request were reused for another person | **Not used**: generation requests carry no cache checkpoint | L0 test on the request builder |
| Retrieval results kept between requests | Yes | **Not kept**; results live only within one invocation | L0 static check; TST-ELG-003 includes an identical question asked first by P-02 (eligible) and then by P-01 (ineligible) |
| Grants or classification cached in a warm function | Yes — revocation and upward reclassification would be ignored | **Not cached** across invocations | L0 static check; TST-CHG-001 and TST-CHG-002 run in a warm function |
| Service-internal caching inside the managed retrieval service | Not relied upon; any such cache would still be subject to the constraint per request | Observed indirectly: every test sends the full constraint each time; mismatches are caught by CTL-014 | TST-ELG-003 identical-question sequence |

**Conclusion:** Episode 02 has **no cache** that could become a second retrieval path. Adding one later needs its own
architecture decision, and its key must include the full eligibility decision.

## 8. Authorization freshness vs knowledge-base freshness

| Change | Episode 02 solves | Evidence | Left to Episode 03 |
|---|---|---|---|
| Grant revoked | Next request uses the new grants (per-request read, no cache) | TST-CHG-001, TST-SEN-003 | Registry propagation guarantees |
| Employee leaves | INACTIVE → no retrieval | TST-SEC-006 | — |
| Section reclassified upward | Verification compares the **current** record and withholds before generation | TST-CHG-002 | Re-indexing so answers resume; the withheld-answer window |
| Section reclassified downward | Stays at the stricter indexed label (safe) until re-index | Design (§5.5) | Propagating the change |
| New document version with different sections | Old chunks fail verification (section version changed) → withheld | TST-CHG-002 pattern | Version-aware re-indexing and removal of old chunks |
| Section or document deleted | No current record → withheld | Verification rule | Deletion propagation from both tiers |

**Why this boundary holds:** Episode 02 keeps **authorization** current at request time (verified for the educational implementation under the tested conditions). It does not keep the
**index** current. That is the next architecture problem.

## 9. Deployment model

| Deployment | Stack name | Variant parameter | Lifetime |
|---|---|---|---|
| Normal | `tla-s01e02-<suffix>` | `none` | One session; cleaned up |
| Experiment 1 — eligibility constraint removed | `tla-s01e02-sen-eligibility` | `eligibility-removed` | Minutes; destroyed immediately after its runs |
| Experiment 2 — label propagation corrupted | `tla-s01e02-sen-labels` | `labels-corrupted` | Minutes; destroyed immediately |
| Experiment 3 — stale token claims used as grants | `tla-s01e02-sen-claims` | `claims-as-grants` | Minutes; destroyed immediately |

**Rules:**
- A variant never shares buckets, knowledge bases, indexes, tables, user pools or functions with the normal deployment.
- Only one variant exists at a time.
- The variant module is packaged only into its own stack; the normal package contains no variant code path.
- **Sequence:** preflight → deploy normal → load fixtures → full suite → experiments 1–3 (each: baseline on normal →
  deploy variant → fixtures → target tests → destroy variant and verify → restored run on normal) → evidence bundle →
  cleanup → verify cleanup.

## 10. Source structure (planned; created during the build)

```
05-implementation/
  app/core/          eligibility.py · classification.py · sections.py · constraints.py · verification.py · audit_record.py · reason_codes.py
  app/query/         handler.py · policy_decision.py · retrieval_gateway.py · response.py · generation.py
  app/ingestion/     handler.py · tier_router.py
  infrastructure/    template.yaml
  scripts/           preflight.py · deploy.py · cleanup.py · tla_ops.py
  tests/             unit tests for app/core (run in public CI; no AWS)
06-validation/
  fixtures/          records/*.md · classification_records.json · personas.json
  harness/           personas.py · canaries.py · inventory.py · faults.py · evidence.py · tests_*.py
  sensitivity/       eligibility_removed.py · labels_corrupted.py · claims_as_grants.py   (test-only; never in the normal package)
```

## 11. Teaching simplifications

| ID | Simplification | Why | Production would | Removes a taught control? |
|---|---|---|---|---|
| TS-E02-01 | One query function hosts the policy decision point, gateway, verification, response and audit as separate modules | One deployable function keeps the flow readable | Separate decision service with its own identity; gateway as its own component | No — the controls are separate modules with separate tests; tier storage and knowledge-base roles stay separated |
| TS-E02-02 | HR status and entitlement grants are two record types in one table, loaded by the fixture loader | Two authorities without two external systems | Integrations with the real HR system and entitlement registry | No — the decision still reads both, versioned, per request |
| TS-E02-03 | The learner's sandbox administrator loads fixtures, injects faults and inventories tiers | Non-interactive testing | Separate operator and evidence roles | No |
| TS-E02-04 | Harness signs personas in with the administrator-initiated auth flow | No browser sign-in | Federated workforce sign-in | No |
| TS-E02-05 | The records system is simulated by a bucket and a classification table | No real document management system | Integration with the records system's classification API and events | No |
| TS-E02-06 | Audit store in the same stack; 1-day logs | Simple cleanup | Separate security account, governed retention | No |
| TS-E02-07 | Relevance threshold is a simple score cut-off | Keeps "cannot answer" behaviour observable | Evaluated answer-quality policy | No — relevance never affects eligibility |
| TS-E02-08 | No throttling, quotas or WAF | Episode 04 | Rate limits and abuse controls | No |

## 12. Candidate visual opportunities (notes for later media; not media production)

- **Two layers of D3:** a tier as a room holding many locked drawers; the constraint as the key that opens only yours.
- **One mixed document split into sections:** each label flowing to its chunks, one section never leaving the records
  system.
- **Measured constraint budget:** 40 grants = 926 bytes against an 8,192-byte budget (observed limits 10,240 and 15,360 bytes); over the limit means refusal, not
  truncation.
- **The negative-operator trap:** `notEquals RESTRICTED` quietly returning an unlabelled chunk.
- **Grants source down:** the whole request path stops before any search.
- **The three experiments side by side:** what was broken, which test failed, what verification did.

## 13. Build status

The design was accepted and the educational implementation was built on 2026-09-15. Validation results are recorded in
[`../06-validation/TRACEABILITY_MATRIX.md`](../06-validation/TRACEABILITY_MATRIX.md), with evidence under
`../07-evidence/implementation-validation-2026-09-15/`.

## 14. As built — differences from this design

| # | This design said | As built | Why |
|---|---|---|---|
| 1 | Verification passes a chunk whose `record_version` equals the current version, **or** whose change was downward (§5.5) | Label, scope **and** version must all equal the current record; any difference withholds | §5.5 also requires the label to equal the current label, so a downward change could never pass. The stricter reading was implemented: a downward reclassification is withheld until re-indexing (an Episode 03 concern, RR-04) |
| 2 | Constraints checked against the measured 15,360-byte limit (§5.4) | An 8,192-byte budget, measured with the builder's serialisation | The build re-measurement found a second, lower limit of 10,240 bytes at the vector store (PLATFORM_VERIFICATION §6). Stricter; about 40 grants still use 926 bytes |
| 3 | Experiment 1 queries both tiers **without** a constraint (§9, TEST_HARNESS_DESIGN §3) | Both tiers for everyone, with a **label-only** constraint: the eligibility clauses are removed | The gateway refuses a search without a constraint. Replacing only the builder keeps the rule "a variant differs by exactly one module", and every section of each tier becomes retrievable for every requester — the fault the experiment needs |
| 4 | Relevance threshold calibrated during the build (§5.5) | 0.60 (method and evidence: `../06-validation/RELEVANCE_CALIBRATION.md`); when the model replies with the no-answer sentence, the uniform response is returned without citations | A non-answer must look like every other non-answer |
| 5 | The query function maps `sub` to the synthetic employee ID (§5.1) | Grants records are keyed by the identity subject and carry the employee ID; history items keep earlier versions | One consistent batch read per request; the same authority |
| 6 | Audit fields as listed in §6 | Adds `verification.record_versions` and `relevance` (`min_score`, `kept`, `omitted` chunk IDs); ingestion quarantine reports are stored as `INGESTION_REPORT` items in the audit table | Needed to reconstruct decisions (TST-OBS-002) and to evidence that relevance never changes eligibility; all content-free |
| 7 | Source structure in §10 | Each request step is its own module: `query/trusted_context.py`, `core/tier_selection.py`, `core/constraints.py`, `query/retrieval_gateway.py`, `core/verification.py`, `core/relevance.py`, `query/generation.py`, `query/response.py`, `core/audit_record.py`; AWS adapters in `adapters/`. Harness modules: `identities`, `observe`, `canaries`, `suites/`, `calibration`, `platform`, `runbook` | One deployment unit without becoming one blob: the control path is visible and every step is tested on its own |
| 8 | TST-SEC-005 removes the fault and continues | The harness first waits for a clean baseline, then removes the fault and waits for access to return (up to 15 minutes) | Removing an explicit Deny took minutes to propagate; every request in that window was refused with zero tier calls |
| 9 | TST-SCALE-001 checks P-10 and the over-limit persona | Also checks, against the deployed service, that the largest constraint the application accepts is accepted with its last grant honoured, and that one above the observed limit is rejected | Turns "the budget sits below the platform's behaviour" into an executed test |
| 10 | Uniform non-answer text "I can't answer that question." (as validated) | "I can't answer that from the information available to me." on every generic no-answer and fail-closed path, and in the model's fixed no-answer instruction | A post-validation wording change: the response model, outcomes and audit records are unchanged. Proved by the local query-path tests; evidence captured before the change keeps the earlier wording |
