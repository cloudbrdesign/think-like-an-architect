# Educational Implementation Design — Veltamere Document Assistant

**Stage:** implementation design · **Date:** 2026-09-14
**Status:**
- **Design:** complete. The platform spikes ran on 2026-09-14 and passed (see [PLATFORM_VERIFICATION.md](PLATFORM_VERIFICATION.md)).
- **Build:** the educational implementation is built. The learner guide is [README.md](README.md).
- **Validation:** the fresh-copy run of 2026-09-14 is in [07-evidence/implementation-validation-2026-09-14](../07-evidence/implementation-validation-2026-09-14/README.md).

```
VERIFIED IDENTITY → TRUSTED TENANT CONTEXT → AUTHORITATIVE AUTHORISATION
→ MANDATORY PRE-RETRIEVAL TENANT BOUNDARY → OWNERSHIP VERIFICATION → GENERATION
```

Companion documents:
- [IMPLEMENTATION_CONTROLS.md](IMPLEMENTATION_CONTROLS.md) — control specification, IAM, audit schema, reason codes
- [COST_AND_CLEANUP.md](COST_AND_CLEANUP.md)
- [TEST_HARNESS_DESIGN.md](../06-validation/TEST_HARNESS_DESIGN.md)

## 1. What the learner will build

A small, working multi-tenant document assistant in the learner's own sandbox AWS account:
- one API with four authenticated routes;
- two small Python functions (query and ingestion);
- a shared retrieval index;
- one table for the tenant registry and ownership records, and a separate audit table;
- a stand-in identity provider;
- a test harness that attacks the deployment, observes the retrieval layer, runs the sensitivity variant and proves
  cleanup.

**The learner should be able to open four files and see the whole isolation argument:**

| File | The argument it makes |
|---|---|
| `app/shared/tenant_context.py` | Tenant context comes only from verified claims and the registry |
| `app/shared/retrieval_scope.py` | **The primary control:** the only place the tenant constraint is built |
| `app/shared/ownership_verification.py` | Defence in depth: retrieved results are checked before generation |
| `infrastructure/template.yaml` | Who is allowed to do what — every role and permission in one file |

## 2. Implementation mechanism

**Decision question:** which mechanism makes the taught controls — trusted identity, tenant derivation, authorisation,
ingestion attribution, retrieval filtering, permission boundaries, fail-closed behaviour and negative testing — most
visible and testable, while staying reproducible, non-interactive, inspectable, destroyable and cheap?

| Option | Visibility of the taught controls | Reproducible / non-interactive | Destroyable | Learner tooling | Verdict |
|---|---|---|---|---|---|
| **A — One CloudFormation template + AWS CLI deploy/cleanup scripts + Python application code + Python test harness** | Every resource and **every IAM permission in one readable file**; controls in named Python modules | Yes (`deploy.sh`, `cleanup.sh`) | Stack deletion plus a verified cleanup script | AWS CLI v2, Python 3, boto3 | **Chosen** |
| B — Terraform + Python | Also readable. Adds a tool, state-file handling and provider-version drift; support for the newest resource types not verified | Yes | `terraform destroy` | Terraform + state | Not chosen: extra machinery teaches nothing about isolation |
| C — AWS CDK | Permissions generated from constructs and helper grants; the boundary hides behind abstractions | Yes | `cdk destroy` | Node.js toolchain + CDK | Not chosen: "framework magic" hides the permission boundary |
| D — AWS SAM | Readable template and convenient function packaging | Yes | Leaves a managed artifact stack and bucket that learners forget | SAM CLI | Not chosen: cleanup-sensitive side resources |
| E — CLI / SDK provisioning scripts only | Each API call visible, but IAM policies scattered across scripts | Yes | Ordered manual teardown with state tracking — error-prone | CLI | Not chosen: teardown and permission review become fragile |
| F — Console steps | Clicks, not artifacts | No | Manual | Browser | Rejected: not reproducible (OPS-003) |

**Why A:**
- **The permission boundary is part of the lesson.** A single declarative template lets a learner answer "who can
  retrieve?" by reading one file. TST-SEC-023 checks the same answer against the deployment.
- **The tenant boundary is application logic, not infrastructure.** It belongs in small, plainly named Python modules
  that tests can import.
- **Stack deletion** gives a dependable teardown; the cleanup script handles only what a stack cannot (emptying buckets,
  the artifact bucket) and then verifies.
- **Resource support is documented** for every type needed, including knowledge bases on S3 Vectors and custom data
  sources (PE-05…PE-07). Deployment was proven by spike SPK-I on 2026-09-14: create and delete both completed.

**Commercial packs are unaffected:** their Terraform + CloudFormation obligation is separate and does not shape this
choice.

## 3. Final educational AWS service mapping

The architecture's candidate mapping, refined by verification. "Status" shows the strongest evidence so far.

| Architectural component | Educational implementation | Change from architecture candidate | Status |
|---|---|---|---|
| Identity provider | Amazon Cognito user pool **standing in for Veltamere's existing identity provider**; tenant membership = administrator-managed group (`tenant-a`, …); one app client | — | Docs (PE-10); claim format pending SPK-G |
| API edge | Amazon API Gateway HTTP API; JWT authorizer (issuer = user pool, audience = app client, route scope `aws.cognito.signin.user.admin`) on every route; access logging | — | Docs (PC-17) |
| Query service (resolver, gateway, verification, answer composer) | AWS Lambda, Python 3.13, 512 MB; own role | — | SDK pending SPK-F |
| Ingestion service | AWS Lambda, Python 3.13, 256 MB; separate role | — | SDK pending SPK-F |
| Invocation boundary | Lambda resource policy: allow the API source ARN; **explicit Deny** for every other caller | Explicit Deny added (CH-01) | Docs (PE-08, PE-09); pending SPK-D |
| Tenant registry and ownership records | Amazon DynamoDB, one table, item types `TENANT#<id>` and `DOC#<id>`, on-demand, strongly consistent reads | — | Docs |
| Security audit store | **Amazon DynamoDB audit table** (separate table and permissions) | Was CloudWatch Logs (CH-05) | Design refinement |
| Document store | Amazon S3 bucket; Block Public Access; TLS-only; objects at `tenants/<tenant_id>/documents/<document_id>/source.md`; bucket policy denies writes except by the ingestion role and reads except by the ingestion role and knowledge-base service role | Bucket-policy write/read restriction added | Docs; pending SPK-C |
| Shared retrieval index + indexing | Amazon Bedrock Knowledge Base (customer-managed), `CUSTOM` data source, direct ingestion from S3 locations with inline attributes `owning_tenant` and `document_id`; vector store Amazon S3 Vectors (1024 dimensions, cosine) | — | Docs (PE-05, PE-06); combination pending SPK-A/B/C/E |
| Embedding model | Amazon Titan Text Embeddings V2 In-Region | — | Docs (PE-03); pending SPK-F |
| Generation model | **Amazon Nova Micro (`amazon.nova-micro-v1:0`) In-Region via Converse**; foundation-model identifier only | Model named (CH-03) | Docs (PE-03); pending SPK-F |
| Region | **us-east-1** | Region named (CH-04) | Docs (PE-03, PE-04) |
| Encryption | S3 SSE-S3; DynamoDB default encryption; S3 Vectors default encryption; TLS in transit | Provider-managed keys (TS-10) | Docs |
| Operational logs | Amazon CloudWatch Logs groups defined in the stack, 1-day retention | — | Docs |
| Bypass detection | Not deployed; permission analysis (TST-SEC-023) instead | — (TS-06) | Design |

## 4. The deployable learner architecture

One stack per deployment (`tla-s01e01-normal`, or `tla-s01e01-sensitivity` for the test-only variant) plus an artifact
bucket created by the deploy script. As built, every resource carries the CloudBrewery lab tag standard:
`Project=CloudBreweryLabs`, `Course=ThinkLikeAnArchitect`, `Season=01`, `Episode=01`, `Environment=Sandbox`,
`ManagedBy=CloudBreweryLabs`, `Variant=normal|sensitivity`, `Purpose=education`, `DeployedWith=CloudFormation`. This replaces
the `tla:*` keys drafted during design, so there is one tag vocabulary.

| Resource | Count | Purpose |
|---|---|---|
| Cognito user pool, app client, tenant groups | 1 / 1 / 3 | Identity stand-in (users are created by the fixture loader) |
| HTTP API, stage, JWT authorizer, 4 routes, access log group | 1 each | API edge |
| Lambda functions + log groups + roles | 2 + 2 + 2 | Query and ingestion services |
| DynamoDB tables | 2 | Registry and ownership; audit |
| S3 document bucket (+ bucket policy) | 1 | Originals |
| S3 vector bucket + index | 1 + 1 | Vector store |
| Bedrock knowledge base + custom data source + service role | 1 + 1 + 1 | Shared retrieval index |
| Artifact bucket (deploy script, outside the stack) | 1 | Function packages |

**Routes:**

| Route | Function | Purpose | Request body (only these fields) |
|---|---|---|---|
| `POST /ask` | query | Ask a question | `question` (string, ≤ 1,000 characters — the documented user query size) |
| `POST /documents` | ingestion | Upload a document | `title` (≤ 120 chars), `content` (Markdown text, ≤ 200 KB) |
| `GET /documents/{document_id}` | ingestion | Open a cited document; refresh its status | — |
| `DELETE /documents/{document_id}` | ingestion | Delete own document | — |

There is **no** route to update ownership, list other tenants' documents, administer tenants or debug. Every response
carries `x-tla-event-id`, the audit record key.

## 5. Implementation components

| Component | Responsibility | Combined or separate — and why |
|---|---|---|
| API edge (managed) | Token verification | Separate: it is TB-1 |
| `app/query/handler.py` | Orchestrates the query path in the order of the principle chain | One function for resolver, gateway, verification and composer. They share one trust zone, and keeping them together keeps decision and constraint in one code path (ADR-003) |
| `app/ingestion/handler.py` | Upload, open, delete | **Separate function and role** from the query service. Combining them would give one identity both retrieval and indexing permissions, hiding the exclusivity boundary (CTL-008, CTL-013) |
| `app/shared/request_schema.py` | Allowlisted request bodies | Shared module |
| `app/shared/tenant_context.py` | Trust transition: verified claims + registry → `TenantContext` | Shared module, used identically by both functions |
| `app/shared/retrieval_scope.py` | Authoritative decision and tenant constraint → `TenantScopedQuery` | **Its own file**, so the primary control is findable, reviewable and replaceable in exactly one place by the sensitivity variant |
| `app/shared/retrieval_client.py` | Calls `Retrieve` only with a `TenantScopedQuery` | Separate from scope, so the client cannot construct constraints |
| `app/shared/ownership.py` | Ownership records, attribution gate, indexing and deletion calls | Ingestion only |
| `app/shared/ownership_verification.py` | **Defence in depth** before generation | Separate file, named and documented as secondary |
| `app/shared/citations.py` | Citation isolation | Shared module |
| `app/query/prompt.py` + `model_client.py` | Bounded generation context; In-Region `Converse` | Query only |
| `app/shared/audit.py` + `reason_codes.py` | Audit records; stable codes | Shared |
| `validation/harness/` | Test harness, fixtures, evidence | Runs on the learner's machine, never deployed |
| `validation/sensitivity/retrieval_scope.py` | **Test-only** replacement for the primary control | Never part of a normal build (section 10) |

## 6. Source structure (planned; created during implementation)

```
05-implementation/
  IMPLEMENTATION_DESIGN.md · IMPLEMENTATION_CONTROLS.md · PLATFORM_VERIFICATION.md · COST_AND_CLEANUP.md   (design)
  README.md                       learner guide, in architecture order
  config/learner.env.example      AWS_REGION, STACK_SUFFIX, AWS_PROFILE (no secrets)
  infrastructure/template.yaml    all resources and IAM in one file
  app/
    query/handler.py  prompt.py  model_client.py
    ingestion/handler.py
    shared/request_schema.py  tenant_context.py  retrieval_scope.py  retrieval_client.py
           ownership.py  ownership_verification.py  citations.py  audit.py  reason_codes.py
  scripts/
    preflight.sh  build.sh  deploy.sh  cleanup.sh  sensitivity-run.sh
    operator/correct_attribution.py   privileged, recorded correction workflow
  spikes/                         platform verification evidence only — not the learner implementation
06-validation/
  harness/  (CLI, suites, canary scanner, evidence writer)  tests/  (component tests of app/shared)
  fixtures/tenants.json  fixtures/documents/{tenant-a,tenant-b,tenant-c,edge-cases}/*.md
  sensitivity/retrieval_scope.py   test-only replacement of the primary control
  results/                        git-ignored run output
cleanup/README.md                 the single documented cleanup flow
```

**As built, differences from the plan above:**
- `app/shared/tenant_claims.py` (strict group-claim parser, CH-12), `registry.py`, `dynamo.py`, `http.py` and
  `build_info.py` were added as small explicit modules.
- `scripts/tla_ops.py` holds the deployment logic that the `.sh` wrappers call (Python and boto3 only; the AWS CLI is
  not required).
- The harness and component tests live under `06-validation/` (`harness/`, `tests/`); run results go to
  `06-validation/results/` (git-ignored); curated evidence goes to `07-evidence/`.
- There is no separate `cleanup/README.md`: the single cleanup flow is in [README.md](README.md#clean-up) and
  [COST_AND_CLEANUP.md](COST_AND_CLEANUP.md).

## 7. Identity flow — what the learner observes

1. The fixture loader creates Tenant A, B and C in the registry and one user per tenant, each in exactly one group.
   **This is the stand-in for Veltamere's identity provider.** The lesson is "tenant context must come from a verified
   authority", not "Cognito is required".
2. `harness identity show --as user-a` prints the decoded access-token claims (subject, `token_use`, `client_id`,
   groups). It does not print the token itself.
3. `harness ask --as user-a --forge tenant-b "…"` sends Tenant B's identifier in the body, query string, header and
   question text.
4. The learner sees:
   - the body field refused with `REQUEST_FIELD_REJECTED`;
   - for the other variants, audit records with `tenant_context = tenant-a` and
     `constraint.value = tenant-a`;
   - no Tenant B document in `retrieved`.
5. The learner opens `tenant_context.py` and sees that it reads only `requestContext.authorizer.jwt.claims`.

## 8. Ingestion flow — what the learner observes

```
USER / REQUEST → VERIFIED TENANT CONTEXT → TRUSTED INGESTION SERVICE → OWNERSHIP RECORD → INDEXED RETRIEVAL METADATA
```

1. `POST /documents {title, content}` as `user-a`.
2. The ingestion service resolves `TenantContext(tenant-a)`, generates `document_id`, stores the original at
   `tenants/tenant-a/documents/<id>/source.md`, and writes `DOC#<id>` with owner `tenant-a`, uploader, time and
   `RECEIVED`.
3. The attribution gate compares record owner, key tenant segment and the attribute value about to be indexed; all must
   equal `tenant-a`.
4. `IngestKnowledgeBaseDocuments` is called with the S3 location and **inline attributes supplied by the service**:
   `owning_tenant = tenant-a`, `document_id = <id>`. Status becomes `INDEXING`.
5. `GET /documents/<id>` refreshes status from `GetKnowledgeBaseDocuments`; `INDEXED` → `AVAILABLE`.
6. `harness inspect document <id>` shows the ownership record, the index status and the audit record side by side.

**Planned negative cases:**

| Input | Expected behaviour |
|---|---|
| Body includes `owning_tenant`, `tenant_id`, `owner` or `document_id` | **Refused** `REQUEST_FIELD_REJECTED`; nothing stored |
| Content says "Owner: Brightmoor Services" (uploaded by `user-a`) | Stored and indexed as **Tenant A's** document; content never sets ownership |
| Record, key and attribute disagree (component-level fault injection) | `QUARANTINED`; no indexing call; `INGESTION_ATTRIBUTION_CONFLICT` |
| Uploader's tenant disabled | Refused `TENANT_DISABLED`; nothing stored |
| `user-a` deletes a Tenant B document by identifier | **Not found** `DOCUMENT_NOT_FOUND_FOR_TENANT`; nothing changed |

## 9. Retrieval flow — where each thing happens

| Step | What the learner can inspect | Where |
|---|---|---|
| Tenant context arrives | `TenantContext(tenant_id, user_id)` | `app/shared/tenant_context.py::resolve()` |
| **The constraint is constructed** | `{"equals": {"key": "owning_tenant", "value": ctx.tenant_id}}` inside a frozen `TenantScopedQuery` | **`app/shared/retrieval_scope.py::authorize_and_scope()` — the primary preventive control** |
| Retrieval occurs | One `Retrieve` call: question as `retrievalQuery.text`; `vectorSearchConfiguration` with the scoped filter and `numberOfResults = 5` fixed | `app/shared/retrieval_client.py::retrieve()` |
| Retrieved ownership is observed | Each result's `metadata.owning_tenant` and `metadata.document_id`, written to the audit record's `retrieved` list **before** verification | `app/query/handler.py` → `app/shared/audit.py::write_decision()` |
| Ownership validation occurs | Owner attribute and `DOC#` record must match the context and be `AVAILABLE` | **`app/shared/ownership_verification.py::verify()` — defence in depth, not the isolation control** |

**Keeping the two controls distinct:**
- The **tenant-constrained retrieval** (CTL-015) is what *prevents* other tenants' content from being retrieved.
- **Ownership verification** (CTL-017) *detects* a failure of that prevention, or of attribution, and withholds the
  response.
- Code comments, module names, audit fields (`constraint` vs `verification_outcome`), learner guide wording and the
  sensitivity test all keep this distinction. Removing CTL-017 would not make the system leak. Removing CTL-015 does,
  and the tests see it at the retrieval layer.

## 10. Deployment sequence

| Step | Command | What happens | Idempotent |
|---|---|---|---|
| 0 | `scripts/preflight.sh` | Read-only checks: CLI and Python versions, credentials and account ID shown, region = configured, models available In-Region, model invocation logging disabled, no existing stack with the same suffix | Yes |
| 1 | `scripts/build.sh normal` | Copies `app/` into `build/normal/`. Asserts no file from `validation/sensitivity/` is present and that `retrieval_scope.py` is byte-identical to source. Zips each function and records SHA-256 | Yes |
| 2 | `scripts/deploy.sh` | Creates the tagged artifact bucket; packages; deploys the stack (named IAM capability); applies the explicit-Deny function resource policies if the template cannot (VE-17); prints outputs | Yes (stack update) |
| 3 | `python -m harness fixtures load` | Registry tenants; Cognito users (random passwords, never written to disk); documents uploaded **through the API as each tenant's user**; waits for `AVAILABLE` serially | Yes (skips existing) |
| 4 | `python -m harness run --suite all` | Validation (TEST_HARNESS_DESIGN) | Yes |
| 5 | `scripts/sensitivity-run.sh` | Separate variant: build → deploy → run → destroy → verify | Yes |
| 6 | `scripts/cleanup.sh` then `python -m harness verify-cleanup` | COST_AND_CLEANUP | Yes |

## 11. Reproducibility plan (TST-OPS-018)

**Fresh-copy deploy for Episode 01 means:**
- a clean clone of the repository at a tagged commit;
- the documented prerequisites installed;
- a sandbox account meeting PLATFORM_VERIFICATION section 1;
- `config/learner.env` created from the example with region, stack suffix and profile;
- running steps 0–6 above **with no console action and no interactive prompt**, producing a harness report in which
  every test has a result and cleanup verification is clean.

**Unavoidable manual prerequisites (explicit, small, justified):**
1. **Have a sandbox account and administrator credentials in it** — the course cannot create accounts for learners.
2. **Create the budget alert** — recommended rather than required; a documented CLI command is provided, and the
   console works too.
3. **Enable model access, only if the account requires it** — VE-18; preflight detects and explains it.

The suite runs twice from fresh copies before the educational implementation can be verified, one of them from a clean
account state (AC-VAL-03).

## 12. Learner journey (architecture order)

| # | Step | The learner does | The learner sees |
|---|---|---|---|
| 1 | Understand the baseline | Read the ADRs and the three diagrams | Where identity, authorisation and the retrieval boundary sit |
| 2 | Deploy the minimum platform | `preflight`, `build`, `deploy` | One template; every permission in one file |
| 3 | Create synthetic tenants | `fixtures load` (tenants and users) | Registry items; one group per user |
| 4 | Establish trusted identity context | `identity show`; forged-tenant request | Verified claims vs untrusted request data |
| 5 | Ingest tenant-owned documents | Uploads through the API | Ownership assigned by the service, not the caller |
| 6 | Inspect ownership | `inspect document` | Record, index status, audit record |
| 7 | Perform authorised retrieval | `ask --as user-a` (own topic) | Answer, citations, `constraint = tenant-a` |
| 8 | Attempt cross-tenant retrieval | `ask --as user-a` (Brightmoor's rate) | No Tenant B documents in `retrieved` |
| 9 | Inspect audit evidence | `inspect event <event_id>` | Who, which tenant, decision, constraint, retrieved IDs — no content |
| 10 | Run attack tests | `run --suite security` | Refusals, fail-closed reason codes, bypass denials |
| 11 | Run the sensitivity test | `sensitivity-run.sh` | The negative tests **failing** when only CTL-015 is removed |
| 12 | Clean up | `cleanup.sh`, `verify-cleanup` | An empty tagged-resource search |
| 13 | Collect portfolio evidence | `evidence bundle` | A redacted results summary and the evidence checklist |

## 13. Teaching simplifications

TS-01…TS-10 from [AWS_SERVICE_MAPPING section 6](../03-architecture/AWS_SERVICE_MAPPING.md#6-educational-implementation-fit)
remain. Added at implementation design:

| ID | Simplification | Why it exists | What production would do | Security consequence in the learner build | Removes the taught control? |
|---|---|---|---|---|---|
| TS-11 | Harness obtains user tokens with the administrator-initiated password flow on the app client | Non-interactive tests without a browser sign-in | Hosted or federated sign-in; no admin auth flow on user-facing clients | Anyone with the sandbox administrator's credentials can mint user tokens — already a privileged path | No |
| TS-12 | Audit table in the same account and stack as the application | One deployable unit; simple cleanup | Audit export to a separate security account with write-once retention | Administrators can alter records | No |
| TS-13 | Opening a document returns its text through the API | Small synthetic Markdown only | Short-lived download links to a server-chosen key after the same ownership check | Response size limits | No |
| TS-14 | The learner's sandbox administrator identity is deployer, operator and harness identity | One set of credentials | Separate deployment role, operator role with approval, read-only evidence role | The privileged path is broader than production's | No |
| TS-15 | 1-day log retention; audit table deleted at cleanup | Cost and cleanup | Governed retention agreed with Legal | Evidence must be exported by the learner before cleanup | No |
| TS-16 | Access tokens with the default user-pool scope; no custom API scope | A custom scope needs the hosted OAuth flow | Resource server with a custom scope for the assistant API | The default scope also lets users edit their own profile; tenant is not in the profile (groups), so isolation is unaffected | No |
| TS-17 | No WAF, throttling plans or per-tenant quotas | Episode 04 | Rate limiting and quotas per tenant | Load and abuse behaviour untested | No |

## 14. Security of the educational implementation

| Rule | How the design meets it |
|---|---|
| No hard-coded AWS credentials | Default credential chain only; functions use roles; test passwords random per run, held in memory |
| No public document buckets | Block Public Access on; TLS-only bucket policy; no public URLs |
| No wildcard permissions without justification | Resource-scoped statements. Justified wildcards: object paths under `tenants/*`; log streams under the function's own log group |
| No caller-trusted tenant IDs | CTL-004; TST-SEC-005 |
| No sensitive production data | Synthetic fixtures only (ASM-009); fictional companies and canaries |
| No unauthenticated APIs | JWT authorizer on every route; no default route |
| No debug bypasses | No debug routes, no override parameters; **no runtime switch disables the tenant constraint** — the sensitivity variant is a separate build and deployment |
| No deliberately weak permanent controls | The only deliberately broken code is `validation/sensitivity/`, deployed only by `sensitivity-run.sh` into a separately named, tagged stack destroyed in the same run |

## 15. Portfolio evidence produced by the implementation

This maps outputs to [PORTFOLIO_EVIDENCE_PLAN.md](../07-evidence/PORTFOLIO_EVIDENCE_PLAN.md). A complete example set,
from CloudBrewery's own fresh-copy run, is in [07-evidence/implementation-validation-2026-09-14](../07-evidence/implementation-validation-2026-09-14/README.md).

| Evidence category | Produced by | Artifact (learner keeps, redacted) |
|---|---|---|
| The architecture you designed | Architecture stage | ADRs, diagrams, own notes on the decision questions |
| The implementation you built | `deploy.sh` output; stack outputs | Deployment summary: stack name, region, resource list without account identifiers; template commit |
| The validation you performed | `harness run --suite all` | `results.json` + `summary.md` |
| Refused cross-tenant attempts | TST-ISO-003, TST-ISO-004, TST-SEC-005 | Response bodies plus audit records showing `constraint` and `retrieved` |
| Attack tests | Security suite | Reason codes per attack; denied bypass calls |
| Proof the tests can fail | `sensitivity-run.sh` | Sensitivity results: both negative tests FAIL; bracketing PASS runs; variant destroyed |
| Audit output | `inspect event` | Two audit records (allowed, denied) with no content |
| Traceability | Harness writes observed results | Completed matrix rows with evidence paths |
| Cleanup | `verify-cleanup` | Empty tagged-resource search, with timestamp |
| Learner reflection | Learner | Largest residual risk; what surprised you; what production would add |

**Claim boundary unchanged:** portfolio evidence of the work you performed — not certification.

## 16. Build-readiness criteria

| Criterion | Status |
|---|---|
| Architecture approved | **Met** (2026-09-14) |
| Load-bearing AWS capabilities sufficiently verified | **Met on evidence (2026-09-14)** — SPK-I, C, A, B, E, F, G, D all PASS in a sandbox account; SPK-B found zero cross-tenant results. Open: VE-09 (production item), VE-11 (confirmed at the first fresh-copy run), VE-18 (partly verified). See PLATFORM_VERIFICATION |
| Learner mechanism selected | **Met** — section 2 |
| Implementation design complete | **Met** — this document, IMPLEMENTATION_CONTROLS, TEST_HARNESS_DESIGN |
| Test strategy executable | **Met in design** — harness, fixtures, guards, sensitivity variant specified |
| Sandbox prerequisites understood | **Met** — PLATFORM_VERIFICATION section 1; CloudBrewery's validation sandbox, region (us-east-1) and budget guardrail are in place |
| Cost target plausible | **Met** — dated estimate far below USD 10 |
| Cleanup designed | **Met** — COST_AND_CLEANUP |
| No unresolved architecture blocker | **Met** — all platform findings are mapping- or implementation-level (CH-01…CH-13); SPK-B, the one spike whose failure would reopen ADR-005, passed |
