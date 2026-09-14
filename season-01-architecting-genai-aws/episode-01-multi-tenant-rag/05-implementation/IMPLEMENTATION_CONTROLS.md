# Implementation Controls — Veltamere Document Assistant

**Stage:** build authorisation and implementation design (E3) · **Date:** 2026-09-14

Every approved architecture control (defined in the ADRs) becomes an implementation specification here. File paths
refer to the source tree in [IMPLEMENTATION_DESIGN section 6](IMPLEMENTATION_DESIGN.md#6-source-structure-planned-created-at-e4).

**E4 status (2026-09-14):** the `EDU` controls are implemented in this folder. Their validation results are in
[07-evidence/e4-validation-2026-09-14](../07-evidence/e4-validation-2026-09-14/README.md).
- **Paths:** the harness lives in `06-validation/harness/`, not `validation/harness/`.
- **Additions:** the strict group-claim parser is its own module, `app/shared/tenant_claims.py` (CH-12). The test-only
  primary-control replacement is `06-validation/sensitivity/retrieval_scope.py`.
- **CTL-010:** the correction workflow removes the misattributed document step by step, and the correct tenant's user
  uploads it again through the normal route. Operators cannot write originals, because the document bucket policy
  admits only the ingestion service.

**Scope marks:**
- **EDU** — implemented in the learner build.
- **EDU-SUB** — the learner build substitutes a check for the control.
- **PROD** — production only.

## 1. Control specification

### Identity and tenant context (ADR-002)

| Control | Architecture purpose | Implementing component | Mechanism | Code / configuration location | Fail-closed condition | Observation point | Validation test | Security consequence if absent |
|---|---|---|---|---|---|---|---|---|
| `CTL-003` EDU | Only verified tokens reach services | API edge | HTTP API JWT authorizer: issuer = user pool URL, audience = app client ID, route scope `aws.cognito.signin.user.admin`; authorizer on all four routes; no default route | `infrastructure/template.yaml` — `HttpApi`, `JwtAuthorizer`, route resources | Missing, invalid, expired, foreign or identity-type token → 401 before invocation | HTTP status; API access log (`$context.authorizer.error`); **absence** of an audit record | TST-SEC-007 | Anonymous or forged callers reach tenant data (SEC-002) |
| `CTL-004` EDU | Tenant context only from verified claims | Tenant Context Resolver | Reads only `event.requestContext.authorizer.jwt.claims`: `sub`, `token_use` (must be `access`), `client_id`, group claim. Exactly one group matching `^tenant-[a-z0-9-]{1,40}$`. Request bodies parsed against an allowlist; unknown fields rejected. Path, query, headers and question text never read for tenant | `app/shared/tenant_context.py::resolve()`; `app/shared/request_schema.py` | `TENANT_CLAIM_MISSING`, `TENANT_CLAIM_AMBIGUOUS`, `REQUEST_FIELD_REJECTED`; any unparseable claim format fails closed | Audit `tenant_context`, `reason_code` | TST-SEC-005, TST-SEC-013 | Tenant substitution (RSK-02) |
| `CTL-005` EDU | Tenant exists and is enabled — checked on every request | Tenant Context Resolver | Strongly consistent `GetItem TENANT#<id>`; `status == ENABLED`; 1-second client timeout | `app/shared/tenant_context.py::resolve()` | Not found `TENANT_UNKNOWN`; disabled `TENANT_DISABLED`; timeout or error `TENANT_REGISTRY_UNAVAILABLE` (503) | Audit `reason_code` | TST-DATA-016, TST-SEC-013, TST-OPS-017 | Disabled tenant served; no stop control during incidents (BUS-001) |
| `CTL-006` EDU | Membership administrator-controlled; one active tenant | Identity stand-in | Tenant membership only as groups created and assigned by the fixture loader with administrator credentials; no tenant user attribute exists | `infrastructure/template.yaml` (user pool, groups); `validation/harness/fixtures.py` | Not a runtime check; a user in several tenant groups is refused by `CTL-004` | SPK-G; TST-SEC-005 case 6 | TST-SEC-005 | User self-assigns a tenant (THR-16) |

### Authorisation and permission boundary (ADR-003)

| Control | Architecture purpose | Implementing component | Mechanism | Code / configuration location | Fail-closed condition | Observation point | Validation test | Security consequence if absent |
|---|---|---|---|---|---|---|---|---|
| `CTL-007` EDU | Decision and constraint in one code path | Retrieval gateway | `authorize_and_scope(ctx, action)` returns a frozen `TenantScopedQuery` only on ALLOW. `retrieve()` accepts only that type (type check) and never builds constraints itself | `app/shared/retrieval_scope.py`; `app/shared/retrieval_client.py` | Wrong type or missing context → `RETRIEVAL_SCOPE_INVALID`; no `Retrieve` call | Audit `decision`, `constraint`; component tests | TST-SEC-013 (case 5), TST-ISO-003, TST-ISO-004 | Decision and enforcement drift apart; retrieval without decision |
| `CTL-008` EDU | Only the gateway can retrieve | IAM | Only `QueryFunctionRole` holds `bedrock:Retrieve`, on the knowledge-base ARN. No other stack role holds it; only the knowledge-base service role holds `s3vectors:QueryVectors` | `infrastructure/template.yaml` — role policies | Other application principals receive AccessDenied | Policy simulation over every stack role | TST-SEC-023, TST-SEC-009 | Any holder retrieves everything unfiltered (PC-04). **Achievable boundary: administrators remain able (CH-02, RR-02)** |
| `CTL-009` EDU | Services invocable only through the API edge | Lambda resource policy | Allow `lambda:InvokeFunction` to `apigateway.amazonaws.com` with `aws:SourceArn` = the API's execute ARN; **explicit Deny** for any request whose `aws:SourceArn` is not that API | `infrastructure/template.yaml` or `scripts/deploy.sh` (VE-17) | Direct invocation (including by the administrator) → AccessDenied | Harness direct-invoke attempt | TST-SEC-009 (case 1), TST-SEC-023 | Forged claim set bypasses token verification (F-01). **Achievable boundary: whoever can edit the resource policy (CH-01)** |
| `CTL-010` EDU | Privileged operations separated and recorded | Operator workflow | `scripts/operator/correct_attribution.py`, run with operator credentials: quarantine → delete from index → delete original → re-ingest as a new document under the correct tenant; writes an audit record `action=OPERATOR_CORRECTION` for each step. Not reachable from any API route | `scripts/operator/correct_attribution.py`; `app/shared/audit.py` | Refuses to run without an explicit `--reason` and target tenant; aborts on any failed step | Audit records; platform management events | TST-SEC-020, TST-SEC-023 | Silent reassignment; unrecorded privileged access |

### Ingestion attribution (ADR-004)

| Control | Architecture purpose | Implementing component | Mechanism | Code / configuration location | Fail-closed condition | Observation point | Validation test | Security consequence if absent |
|---|---|---|---|---|---|---|---|---|
| `CTL-001` EDU | Every chunk carries exactly one owner and a document ID | Ingestion service; index | Inline attributes `owning_tenant`, `document_id` on every `IngestKnowledgeBaseDocuments` call; no call path without them | `app/shared/ownership.py::index_document()` | Missing attribute at retrieval → `OWNERSHIP_MISMATCH` (withhold) | Audit `retrieved[].owner_attribute`; SPK-E | TST-ISO-001…004, TST-SEC-022 | Unowned chunks; filters cannot protect them |
| `CTL-011` EDU | Owner assigned server-side from tenant context | Ingestion service | Upload body allowlist (`title`, `content`). Server-generated UUID `document_id`. Key `tenants/<tenant>/documents/<id>/source.md`. `PutItem DOC#<id>` with `attribute_not_exists` and fields `owner`, `uploader`, `created_at`, `status=RECEIVED`, `title`. Then indexing with inline attributes | `app/ingestion/handler.py::upload()`; `app/shared/ownership.py::create_document()` | Owner or ID fields in the body → `REQUEST_FIELD_REJECTED`; `PutItem` conflict → error, nothing indexed | Ownership record; index document status; audit | TST-SEC-019, TST-ISO-001, TST-ISO-002 | Caller chooses owner; content planted in a competitor's answers |
| `CTL-012` EDU | Inconsistent attribution never indexed | Ingestion service | `attribution_gate(ctx, record, key, attributes)`: record owner = key tenant segment = attribute owner = `ctx.tenant_id`; tenant `ENABLED`; values match the tenant pattern | `app/shared/ownership.py::attribution_gate()` | Any mismatch or missing value → status `QUARANTINED`, **no** indexing call, `INGESTION_ATTRIBUTION_CONFLICT` | Ownership status; index status (absent); audit | TST-ASM-010 (a) (component level), TST-SEC-013 (case 7) | Wrong owner indexed |
| `CTL-013` EDU | Ownership immutable; indexing exclusive | Ingestion service; IAM; bucket policy | No update route. `UpdateItem` on `DOC#` always carries `ConditionExpression owner = :owner` and never sets `owner`. Only `IngestionFunctionRole` holds `IngestKnowledgeBaseDocuments`, `DeleteKnowledgeBaseDocuments`, `GetKnowledgeBaseDocuments` (+ the dependent actions, CH-07). Document bucket policy denies `s3:PutObject` except by that role | `app/shared/ownership.py`; `infrastructure/template.yaml` | Ownership change attempt → no route (404/405) or conditional failure; other principals → AccessDenied | HTTP; audit; policy simulation | TST-SEC-020, TST-SEC-023 | Mutable ownership moves documents across the boundary |
| `CTL-014` EDU | Open and delete only own documents; deletion propagates | Ingestion service | `GetItem DOC#<id>`; owner ≠ context → 404. Delete: `status → DELETING` (conditional), `DeleteKnowledgeBaseDocuments`, `DeleteObject`; `GET` refresh sets `DELETED` when the index reports the document gone | `app/ingestion/handler.py::open_document()`, `delete_document()`; `app/shared/ownership.py` | Other tenant's ID → `DOCUMENT_NOT_FOUND_FOR_TENANT` (no existence disclosure) | HTTP; ownership status; index status; audit | TST-DATA-014, TST-SEC-009 (case 4) | Cross-tenant open or delete by identifier |

### Retrieval boundary (ADR-005)

| Control | Architecture purpose | Implementing component | Mechanism | Code / configuration location | Fail-closed condition | Observation point | Validation test | Security consequence if absent |
|---|---|---|---|---|---|---|---|---|
| `CTL-015` EDU — **PRIMARY** | Mandatory single-tenant constraint during the search | Retrieval gateway → index | `build_tenant_filter(ctx)` returns `{"equals": {"key": "owning_tenant", "value": ctx.tenant_id}}` after re-validating the tenant pattern. It takes no other input. `retrieve()` always sends it in `vectorSearchConfiguration.filter` with `numberOfResults = 5` | **`app/shared/retrieval_scope.py`** (the only file the sensitivity variant replaces) | Pattern invalid or context absent → `RETRIEVAL_SCOPE_INVALID`; no call | Audit `constraint` and `constraint_sha256` | TST-ISO-003, TST-ISO-004, **TST-SEN-011**, TST-SEC-013 | Every tenant's chunks become candidates — the defining weakness of the shared model |
| `CTL-016` EDU | Question text cannot change scope | Retrieval gateway | Question used only as `retrievalQuery.text`. No `implicitFilterConfiguration`, reranking, query transformation or tool use. Search parameters are constants. Body accepts only `question` | `app/shared/retrieval_client.py`; `app/shared/request_schema.py` | Extra fields → `REQUEST_FIELD_REJECTED` | Audit `constraint` identical across prompts | TST-SEC-006, TST-SEC-008 | Prompt shapes retrieval scope (SEC-005) |
| `CTL-017` EDU — **DEFENCE IN DEPTH** | Detect a broken constraint or attribution before generation | Retrieval gateway | For every result: `metadata.owning_tenant == ctx.tenant_id`; `BatchGetItem DOC#<document_id>` owner == context and `status == AVAILABLE`. Owner mismatch or missing → withhold entire response. Status not available → discard that result | **`app/shared/ownership_verification.py::verify()`** — module docstring: *"Detective control. It is not the tenant isolation control; see retrieval_scope.py."* | Mismatch → `OWNERSHIP_MISMATCH` (generic 500-class response); lookup failure → `OWNERSHIP_LOOKUP_FAILED` (503); nothing passed to the model | Audit `verification_outcome`, `discarded_count` | TST-SEC-022, TST-DATA-014; also fires during TST-SEN-011 | Detected divergence reaches the model and the user |
| `CTL-018` EDU | Citations disclose nothing beyond own verified documents | Answer composer | Verified chunks labelled `[D1]…[Dn]` in the prompt; the model cites labels; the composer maps labels to `{document_id, title, location}` from ownership records. Unknown labels removed. Storage keys, index IDs, scores and raw metadata never returned | `app/shared/citations.py::build()` | Unmappable reference removed; nothing else exposed | Response `citations`; audit `cited_document_ids` ⊆ verified | TST-SEC-021 | Leakage through citations and metadata (RSK-15) |

### Audit and observability (ADR-006)

| Control | Architecture purpose | Implementing component | Mechanism | Code / configuration location | Fail-closed condition | Observation point | Validation test | Security consequence if absent |
|---|---|---|---|---|---|---|---|---|
| `CTL-019` EDU | One content-free record per request | Query and ingestion functions | `write_decision()` `PutItem` (condition `attribute_not_exists(event_id)`) after verification and **before** generation; `finalize()` `UpdateItem` with citations and outcome. Denials write a single record | `app/shared/audit.py`; audit table in `infrastructure/template.yaml` | Write failure before generation → `AUDIT_WRITE_FAILED` (503), no generation. Finalize failure → answer returned, record left `outcome=PENDING`, operational error logged | Harness `GetItem` by `x-tla-event-id` | TST-OPS-015; all isolation tests | Exposure cannot be investigated (RSK-10) |
| `CTL-020` EDU | Operational logs contain no content | Both functions; API edge | Logger writes only allowlisted fields (`event_id`, route, reason code, latency, error class); never events, bodies, questions, chunks or answers. API access log format contains no body. 1-day retention | `app/shared/audit.py` (log helper); `infrastructure/template.yaml` log groups | Not a runtime condition; code review plus scan | Harness filters log groups for canary and question strings | TST-OPS-015 | Logs become a second copy of tenant data |
| `CTL-021` PROD / EDU-SUB | Detect retrieval by unexpected principals | Platform | **Production:** data events for knowledge-base resources + alarm on any caller ≠ gateway role. **Learner:** TST-SEC-023 permission analysis (TS-06) | — (production) | — | — | TST-SEC-023 (substitute) | Bypass unnoticed |

### Model boundary and data placement (ADR-001, ADR-007)

| Control | Architecture purpose | Implementing component | Mechanism | Code / configuration location | Fail-closed condition | Observation point | Validation test | Security consequence if absent |
|---|---|---|---|---|---|---|---|---|
| `CTL-002` EDU | Tenant data protected and in region | Stack | Block Public Access; TLS-only bucket policy; default encryption for S3, DynamoDB and S3 Vectors; all resources in the configured region; preflight refuses a mismatched region | `infrastructure/template.yaml`; `scripts/preflight.sh` | Region mismatch → deploy refused | Configuration review; stack outputs | Review (SEC-011, CMP-002) | Public or unencrypted tenant data; out-of-region storage |
| `CTL-022` EDU | Model sees only verified context; no tools or memory | Answer composer | Fixed system instructions + question + verified chunks wrapped as untrusted document content; `Converse` with no tool configuration, no history, no cache | `app/query/prompt.py::build_messages()`; `app/query/model_client.py` | Model error → `MODEL_INVOCATION_FAILED`; no fallback | Code review; audit (one decision per request) | TST-SEC-008, TST-SEC-006 | Model with tools or extra data; injection gains a path |
| `CTL-023` EDU | In-region processing | Model client; IAM | Generation model is an In-Region foundation-model ID (`amazon.nova-micro-v1:0`). Deploy script rejects IDs with a geographic or global profile prefix. Query role granted `bedrock:InvokeModel` only on `arn:aws:bedrock:<region>::foundation-model/amazon.nova-micro-v1:0`; knowledge-base role only on the In-Region embedding model | `scripts/deploy.sh`; `infrastructure/template.yaml`; `app/query/model_client.py` | Profile ID or other region → AccessDenied → `MODEL_INVOCATION_FAILED` | SPK-F; configuration review | Review (CMP-002) | Prompts containing tenant content processed out of region |
| `CTL-024` EDU | Model invocation logging not capturing content | Preflight; harness | Preflight reads the account's model invocation logging configuration in the region and refuses to continue if enabled (override requires an explicit acknowledgement flag that is recorded in the results) | `scripts/preflight.sh`; `validation/harness/checks.py` | Enabled → deploy halted; TST-OPS-015 FAIL | Preflight output | TST-OPS-015 | Prompts with tenant content written to logs |

## 2. IAM design

**Key property:** only the intended retrieval gateway can perform tenant retrieval through the normal application path.

**Achievable boundary (stated without overclaiming):**
- Within the deployed application, only `QueryFunctionRole` can call `Retrieve`, only `IngestionFunctionRole` can index
  or delete documents, and only the API can invoke either function.
- **Account administrators** — anyone who can edit IAM or resource policies, including the learner's own sandbox
  identity — **can still retrieve, invoke or re-grant access**. That is the privileged path (RR-02).
- Production reduces it with organisation guardrails, separate operator roles and data-event alarms.

| Relationship | Principal | Allowed actions | Resources | Notes |
|---|---|---|---|---|
| API invocation | `apigateway.amazonaws.com` | `lambda:InvokeFunction` | Query and ingestion functions, with `aws:SourceArn` = this API | Explicit Deny for any other source (CTL-009) |
| Retrieval gateway execution | `QueryFunctionRole` | `bedrock:Retrieve` | This knowledge base | **Only holder** |
| | | `bedrock:InvokeModel` | `foundation-model/amazon.nova-micro-v1:0` in the region | No inference-profile ARNs |
| | | `dynamodb:GetItem`, `dynamodb:BatchGetItem` | Registry table | Reads `TENANT#` and `DOC#` items |
| | | `dynamodb:PutItem`, `dynamodb:UpdateItem` | Audit table | No reads of audit data |
| | | `logs:CreateLogStream`, `logs:PutLogEvents` | Its own log group | — |
| | | **Not granted:** S3, S3 Vectors, ingestion, registry writes | — | — |
| Ingestion execution | `IngestionFunctionRole` | `s3:PutObject`, `s3:GetObject`, `s3:DeleteObject` | `document-bucket/tenants/*` | — |
| | | `dynamodb:GetItem`, `dynamodb:PutItem`, `dynamodb:UpdateItem` | Registry table; writes limited to `DOC#` keys with a leading-key condition | Cannot modify tenants |
| | | `bedrock:IngestKnowledgeBaseDocuments`, `bedrock:DeleteKnowledgeBaseDocuments`, `bedrock:GetKnowledgeBaseDocuments`, `bedrock:StartIngestionJob`, `bedrock:AssociateThirdPartyKnowledgeBase` | This knowledge base | **Only holder** (CH-07) |
| | | `dynamodb:PutItem`, `dynamodb:UpdateItem` | Audit table | — |
| | | `logs:CreateLogStream`, `logs:PutLogEvents` | Its own log group | — |
| | | **Not granted:** `bedrock:Retrieve`, `bedrock:InvokeModel`, S3 Vectors | — | — |
| Knowledge-base service | `KnowledgeBaseServiceRole`, trusted by `bedrock.amazonaws.com` with `aws:SourceAccount` and `aws:SourceArn` = this knowledge base | `bedrock:InvokeModel` | In-Region Titan Text Embeddings V2 | — |
| | | `s3vectors:PutVectors`, `GetVectors`, `DeleteVectors`, `QueryVectors`, `GetIndex` | This index | — |
| | | `s3:GetObject` | `document-bucket/tenants/*` | PE-14 |
| Ownership registry | — | — | Table access only through the roles above | Onboarding writes `TENANT#` with operator credentials |
| Document store (bucket policy) | Everyone | **Deny** `s3:PutObject` unless principal = `IngestionFunctionRole`; **Deny** `s3:GetObject` unless principal ∈ {`IngestionFunctionRole`, `KnowledgeBaseServiceRole`}; **Deny** non-TLS | Document bucket | Deletion stays possible for cleanup |
| Audit and logging | Functions | Write only | Audit table; own log groups | Harness reads audit as the operator |
| Test harness / operator | Learner sandbox administrator (TS-14) | Cognito admin (create users, set passwords, admin auth, groups); registry writes (tenant fixtures, disable); audit and registry reads; `bedrock-agent` document status; `iam:SimulatePrincipalPolicy`; tag search; operator-scoped `Retrieve` for non-vacuity preconditions | Stack resources | **Privileged path** — every privileged harness action is labelled in the results file |
| Deployer | Learner sandbox administrator | Stack creation with named IAM capability; artifact bucket | Account | Not part of the application's trust model |

## 3. Security audit schema (`tla-audit/1`)

One item per request in the audit table, keyed by `event_id`. **Never logged:** question text, retrieved chunks,
generated answer, document content, tokens.

| Field | Type | Example | Purpose |
|---|---|---|---|
| `event_id` | string (UUID) | `3f2a…` | Key; returned as `x-tla-event-id` |
| `schema` | string | `tla-audit/1` | Versioning |
| `timestamp` | ISO-8601 UTC | `2026-…Z` | When |
| `variant` | string (build-time constant) | `normal` / `sensitivity` | Which build produced the record; not a runtime switch |
| `route`, `action` | string | `POST /ask`, `ask` | What |
| `request_id` | string | API request ID | Join with edge access log |
| `user_id` | string | token `sub` | **Who** (pseudonymous) |
| `token_issuer`, `client_id` | string | user pool issuer, app client | Trusted source |
| `tenant_context` | string or `NONE` | `tenant-a` | **Which tenant** the verified identity mapped to |
| `decision` | `ALLOW` / `DENY` | `ALLOW` | Authorisation outcome |
| `reason_code` | enum (section 4) | `ALLOWED` | Why |
| `failed_control` | string or null | `CTL-005` | Which control stopped the request |
| `constraint` | object or `NONE` | `{"attribute":"owning_tenant","operator":"equals","value":"tenant-a"}` | **Which retrieval boundary** was applied |
| `constraint_sha256` | string | hash of canonical JSON | Tamper-evident comparison across runs |
| `knowledge_base_id` | string | `KB…` | Which index |
| `retrieved` | list | `[{"document_id":"…","owner_attribute":"tenant-a"}]` | What crossed the retrieval boundary, **before** verification — the primary isolation observation point |
| `verification_outcome` | enum | `PASSED` / `DISCARDED` / `OWNERSHIP_MISMATCH` / `LOOKUP_FAILED` / `NOT_APPLICABLE` | Defence-in-depth result |
| `discarded_count` | number | `0` | Non-available results removed |
| `cited_document_ids` | list | `["…"]` | What the user was shown |
| `document_id` | string or null | upload, open, delete target | Ingestion routes |
| `outcome` | enum | `ANSWERED` / `DENIED` / `WITHHELD` / `UPLOADED` / `QUARANTINED` / `OPENED` / `DELETING` / `ERROR` / `PENDING` | Result |
| `status_code` | number | `200` | HTTP status |
| `question_length` | number | `64` | Diagnostics without content |
| `latency_ms` | number | `1830` | NFR-001 review |

## 4. Failure reason codes

These are stable, machine-observable codes. The E2 architecture names (ADR-006) map to them as shown.

| Reason code | E2 name | Raised by | HTTP | Meaning |
|---|---|---|---|---|
| `AUTH_TOKEN_MISSING` | (edge) | API edge | 401 | No token; **no audit record** — observed at the edge |
| `AUTH_TOKEN_INVALID` | (edge) | API edge | 401 | Signature, issuer, audience, expiry or scope failed; **no audit record** |
| `REQUEST_FIELD_REJECTED` | `REQUEST_FIELD_REJECTED` | Request schema | 400 | Undocumented body field, including any tenant or owner field |
| `TENANT_CLAIM_MISSING` | `TENANT_CLAIM_MISSING` | Resolver | 403 | No subject, wrong token use, or no tenant group |
| `TENANT_CLAIM_AMBIGUOUS` | `TENANT_CLAIM_AMBIGUOUS` | Resolver | 403 | More than one tenant group, or unparseable format |
| `TENANT_UNKNOWN` | `TENANT_UNKNOWN` | Resolver | 403 | Tenant not in registry |
| `TENANT_DISABLED` | `TENANT_DISABLED` | Resolver | 403 | Registry status not `ENABLED` |
| `TENANT_REGISTRY_UNAVAILABLE` | `REGISTRY_UNAVAILABLE` | Resolver | 503 | Registry read failed or timed out |
| `RETRIEVAL_SCOPE_INVALID` | `CONSTRAINT_UNBUILDABLE` | Retrieval scope | 403 | Constraint could not be built; no retrieval |
| `OWNERSHIP_MISMATCH` | `OWNERSHIP_MISMATCH` | Ownership verification | 500 | Retrieved owner ≠ context or missing — response withheld; security event |
| `OWNERSHIP_LOOKUP_FAILED` | (part of `REGISTRY_UNAVAILABLE`) | Ownership verification | 503 | Ownership records unreadable — response withheld |
| `INGESTION_ATTRIBUTION_CONFLICT` | `ATTRIBUTION_INCONSISTENT` | Attribution gate | 409 | Record, key and attribute disagree — quarantined |
| `DOCUMENT_NOT_FOUND_FOR_TENANT` | `NOT_FOUND_FOR_TENANT` | Document routes | 404 | Unknown or another tenant's document |
| `AUDIT_WRITE_FAILED` | (fail-closed table) | Audit | 503 | Record could not be written before generation |
| `MODEL_INVOCATION_FAILED` | (new) | Model client | 502 | Generation failed; no fallback |
| `ALLOWED` | `ALLOWED` | — | 200/202 | Success |
