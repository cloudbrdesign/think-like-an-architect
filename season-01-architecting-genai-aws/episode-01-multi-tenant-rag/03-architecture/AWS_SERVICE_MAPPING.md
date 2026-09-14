# AWS Service Mapping — Veltamere Document Assistant

**Stage:** architecture · **Status:** candidate implementation mapping — approved with the architecture on 2026-09-14, subject to platform verification ([PLATFORM_VERIFICATION.md](../05-implementation/PLATFORM_VERIFICATION.md); final educational mapping in [IMPLEMENTATION_DESIGN.md](../05-implementation/IMPLEMENTATION_DESIGN.md#3-final-educational-aws-service-mapping)) · **Date:** 2026-09-14

## 1. How this mapping was made

The mapping was made **after** the patterns and decisions ([ADR-001](../04-decisions/ADR-001-tenant-isolation-model.md) to
[ADR-007](../04-decisions/ADR-007-model-invocation-boundary.md)). Each service was compared because it implements an
architectural requirement. No service is included because it belongs to the Season 1 technology stack. For every
selected service this document answers four questions:

**What requirement does it help satisfy? What architectural role does it play? What trust is placed in it? What failure
would matter?**

Service capabilities change quickly. Every capability the design relies on is listed with a **dated source** in the
currency check (section 4). Items that can only be confirmed in a real account are listed for platform verification
(section 5). **Nothing has been deployed; no AWS resources exist.**

## 2. Mapping

| Architectural component | AWS service (educational implementation) | Requirements | Architectural role | Trust placed in it | Failure that would matter |
|---|---|---|---|---|---|
| Identity provider | **Veltamere's existing identity provider** in the scenario. **Learner stand-in:** Amazon Cognito user pool, membership as administrator-managed groups (TS-01) | SEC-002, SEC-003, CON-004 | Issues signed access tokens with subject and one tenant membership | Signs tokens; membership correct and not user-writable (CTL-006) | Membership writable by users; user in the wrong group; signing key compromise |
| API edge | Amazon API Gateway HTTP API with a JWT authorizer on every route | SEC-002, SEC-009 | Verifies tokens before any service runs; passes verified claims (CTL-003) | Correct signature, issuer, audience/client, expiry and scope verification (PC-17) | A route without the authorizer; scope not required (PC-18) |
| Query service (resolver, retrieval gateway, answer composer) | AWS Lambda function with its own execution role | SEC-003, SEC-004, SEC-005, SEC-008, FUN-001 | Trust transition and **primary enforcement point** (CTL-004, CTL-005, CTL-007, CTL-015–CTL-018, CTL-022) | Runs only the gateway code; invocable only by the API edge (CTL-009) | A code path calling retrieval without the constraint; invocation permitted to other principals |
| Ingestion service | AWS Lambda function with a **separate** execution role | SEC-006, SEC-007, DATA-001, FUN-002, FUN-003 | Write-path enforcement point (CTL-011–CTL-014) | Sole writer of ownership records, originals and indexed documents | Holding retrieval permission (it must not); accepting owner fields |
| Tenant registry and ownership records | Amazon DynamoDB table (TS-02) | BUS-001, DATA-001, SEC-008 | Authoritative tenant status and document ownership | Registry written only by onboarding; ownership only by ingestion | Writable by the query service or users; lookup failure mishandled as allow |
| Document store | Amazon S3 bucket, public access blocked, encrypted | SEC-011, CMP-002, DATA-001 | Originals at `tenants/<tenant_id>/documents/<document_id>` | Readable only by ingestion service and indexing pipeline | Readable by other roles; a citation linking to storage directly |
| Shared retrieval structure and indexing pipeline | **Amazon Bedrock Knowledge Bases** — a customer-managed knowledge base with a **custom data source** and **direct ingestion** (attributes supplied inline by the ingestion service) | SEC-001, SEC-004, DATA-002, FUN-001, NFR-002 | Parses, chunks, embeds; evaluates the gateway's constraint in `Retrieve` (PC-01, PC-07) | Executes the constraint correctly; does not decide scope | Anyone else holding retrieval or ingestion permission (PC-04, PC-05); implicit filtering enabled (PC-02) |
| Vector store | **Amazon S3 Vectors** index behind the knowledge base | SEC-001, NFR-004, CON-008 | Stores vectors and filterable attributes; evaluates filters during search (PC-09, PC-10) | Correct filter evaluation | Filter evaluation defect (RR-05); metadata limits (PC-10, PC-12) |
| Embedding model | Amazon Bedrock embedding model used by the knowledge base, in-region | FUN-001, CMP-002 | Embeds chunks and questions | Processes content in-region | Model unavailable in the contracted region (VE-06) |
| Generation model | Amazon Bedrock runtime (Converse) with an **in-region** model identifier; no cross-region inference profile | FUN-001, SEC-005, CMP-002 | Generates answers from the bounded context (CTL-022, CTL-023) | Processes only what the gateway sends; no tools | Cross-region routing (PC-23); invocation logging capturing content (PC-21) |
| Encryption | AWS KMS — provider-managed keys in the learner build (TS-10); customer-managed keys in production | SEC-011 | Encryption at rest for stores and logs (CTL-002) | Key policies restrict use | Over-broad key policies |
| Security audit store and operational logs | Amazon CloudWatch Logs — **separate** log groups with separate read permissions (TS-07) | OPS-001, OPS-002, CMP-001 | CTL-019, CTL-020 | Only the security role reads audit records | Content written to logs; audit group readable by service operators |
| Bypass detection | AWS CloudTrail **data events** for knowledge-base resources, with an alarm on unexpected principals — production; learner build uses TST-SEC-023 instead (TS-06) | SEC-009, RSK-08 | CTL-021 (PC-22) | Records every retrieval call and its caller | Data events not enabled; alarm not wired |
| Permissions | AWS IAM — one role per function; retrieval permission only on the query role; ingestion permission only on the ingestion role | SEC-009, SEC-010 | CTL-008, CTL-009, CTL-013 | Policies express exclusivity | Drift: an extra role gains retrieval permission (RR-06) |

## 3. Considered and not selected

| Candidate | What it offers | Why it was not selected here |
|---|---|---|
| Amazon Bedrock **Managed** Knowledge Base with ACL-aware retrieval | Fully managed store; document-level access lists filtered by a `userContext` | AWS states that ACL awareness **"is not authorization"** and cannot verify the user context supplied. Access lists name users by email (`Type: USER`) — the per-user list pattern rejected in ADR-001 Option D. The combined retrieve-and-generate operation is unavailable for this type (PC-15, PC-16). Could be revisited for per-user permissions in a later episode |
| `RetrieveAndGenerate` (combined operation) | Retrieval and generation in one call, with citations | No checkpoint between retrieval and generation for CTL-017; citations carry storage locations and metadata (PC-14) — ADR-007 Option A |
| Implicit metadata filtering | A model generates the retrieval filter from the user's query | Lets question text shape the retrieval scope — forbidden by SEC-005 and CTL-016 (PC-02) |
| One knowledge base per tenant | Resource separation | ADR-001 Option A; the per-account knowledge-base quota is not adjustable (PC-06) |
| Amazon OpenSearch Serverless vector collection | Mature vector search, hybrid search, richer filters | Capable, with a larger operational and capacity-management surface than the learner implementation needs. **Preferred evolution** if hybrid search or sustained query volume requires it. Collection groups can now scale to zero OCUs (PC-13); cost to be estimated during platform verification |
| Amazon Aurora PostgreSQL with vector extension | SQL plus vectors | Its documented filtering is applied after the vector index scan unless iterative scans are enabled, which can reduce recall for selective tenant filters (PC-11); a database to operate |
| S3 data source with `.metadata.json` files beside documents | Filter attributes from sidecar files synchronised by the service | The sidecar object would be a second, separately writable source of ownership (PC-08) — ADR-004 prefers attributes supplied inline by the ingestion service (PC-07) |
| Amazon Verified Permissions (dedicated policy decision point) | Centralised policy evaluation; prior art builds retrieval filters from its decisions (PC-25) | One policy today (ADR-003 Option B). **Trigger to adopt:** shared content, administrator-only content or customer-managed policies |
| Cross-region inference profiles | Higher throughput and availability | Routes requests to other regions (PC-23) — violates CMP-002 |
| Tenant stored as a custom user attribute in the learner identity provider | Simple claim | Application clients can write attributes by default, and the default access-token scope allows users to modify their own profile (PC-19, PC-20). Groups are used instead (TS-01) |
| Model invocation logging | Full prompt and response capture for debugging | Captures tenant content in logs (PC-21); disabled (CTL-024) |

## 4. Currency check

All sources were read on **2026-09-14**. A capability claim that cannot be traced to a row below must not appear in the
implementation or the video.

| ID | Capability, as documented | The design relies on it for | Source |
|---|---|---|---|
| PC-01 | Knowledge-base `Retrieve` accepts a `filter` in `vectorSearchConfiguration`, with operators including `equals`, `in`, `andAll` and `orAll` | CTL-015 equality constraint | [Configure and customize queries](https://docs.aws.amazon.com/bedrock/latest/userguide/kb-test-config.html) · [Retrieve API](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_agent-runtime_Retrieve.html) |
| PC-02 | **Implicit metadata filtering**: the knowledge base "generates and applies a retrieval filter based on the user query and a metadata schema" using a model | CTL-016 prohibition | [Configure and customize queries](https://docs.aws.amazon.com/bedrock/latest/userguide/kb-test-config.html) |
| PC-03 | Service-reserved metadata fields cannot be overridden | ADR-004 platform evidence | [Configure and customize queries](https://docs.aws.amazon.com/bedrock/latest/userguide/kb-test-config.html) |
| PC-04 | "All data that you sync from your data source becomes available to anyone with `bedrock:Retrieve` permissions to retrieve the data" | CTL-008 exclusivity | [Connect to Amazon S3 for your knowledge base](https://docs.aws.amazon.com/bedrock/latest/userguide/s3-data-source-connector.html) |
| PC-05 | The Service Authorization Reference lists no condition keys for `Retrieve`, `RetrieveAndGenerate` or the knowledge-base document ingestion actions that could restrict a call to one tenant's filter or content (**re-confirm directly during platform verification — VE-01**) | CTL-008, CTL-013 exclusivity rather than conditional policies | [Actions, resources, and condition keys for Amazon Bedrock](https://docs.aws.amazon.com/service-authorization/latest/reference/list_bedrock.html) |
| PC-06 | Quotas (per account, per region, stated as not adjustable): 100 knowledge bases; 20 `Retrieve` and 20 `RetrieveAndGenerate` requests per second; 1 concurrent ingestion job per knowledge base; 25 files per `IngestKnowledgeBaseDocuments` request (**re-confirm in Service Quotas during platform verification — VE-02**) | ADR-001 platform evidence; cost and scale inflection points | [Amazon Bedrock endpoints and quotas](https://docs.aws.amazon.com/general/latest/gr/bedrock.html) |
| PC-07 | Direct ingestion: a **custom** data source accepts document content (inline or from an S3 location) with metadata defined **inline**; an **S3** data source accepts metadata only from S3 metadata files | ADR-004 implementation of CTL-011 | [Ingest documents directly](https://docs.aws.amazon.com/bedrock/latest/userguide/kb-direct-ingestion-add.html) · [Ingest changes directly](https://docs.aws.amazon.com/bedrock/latest/userguide/kb-direct-ingestion.html) |
| PC-08 | S3 data source metadata is a `fileName.extension.metadata.json` object in the same location as the document, up to 10 KB | Rejection of sidecar ownership files | [Connect to Amazon S3 for your knowledge base](https://docs.aws.amazon.com/bedrock/latest/userguide/s3-data-source-connector.html) |
| PC-09 | S3 Vectors "performs vector search and filter evaluation in tandem"; filtered queries may return fewer than top K results | CTL-015 evaluated during search | [S3 Vectors metadata filtering](https://docs.aws.amazon.com/AmazonS3/latest/userguide/s3-vectors-metadata-filtering.html) |
| PC-10 | With Bedrock Knowledge Bases, up to 1 KB of custom metadata and 35 metadata keys per vector in S3 Vectors; S3 Vectors "is best suited for infrequent query workloads" | Attribute budget; scale inflection | [Prerequisites for your own vector store](https://docs.aws.amazon.com/bedrock/latest/userguide/knowledge-base-setup.html) |
| PC-11 | Aurora PostgreSQL knowledge-base filtering "is applied after the HNSW index scan" without iterative scans | Rejection of that store | [Prerequisites for your own vector store](https://docs.aws.amazon.com/bedrock/latest/userguide/knowledge-base-setup.html) |
| PC-12 | S3 Vectors limits: 10,000 vector indexes per vector bucket; up to 2 KB filterable metadata per vector | Cell evolution headroom | [S3 Vectors limitations](https://docs.aws.amazon.com/AmazonS3/latest/userguide/s3-vectors-limitations.html) |
| PC-13 | OpenSearch Serverless collection groups can set minimum capacity to 0 OCUs for indexing and search | Evolution cost note | [OpenSearch Serverless capacity limits](https://docs.aws.amazon.com/opensearch-service/latest/developerguide/serverless-scaling.html) |
| PC-14 | `Retrieve` results include `content`, `location` (for example `s3Location.uri`, `customDocumentLocation.id`), `metadata` and `score`; `RetrieveAndGenerate` citations include `retrievedReferences` with `location` and `metadata` | CTL-018 citation isolation | [Retrieve API](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_agent-runtime_Retrieve.html) · [RetrieveAndGenerate API](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_agent-runtime_RetrieveAndGenerate.html) |
| PC-15 | `RetrieveAndGenerate` "cannot be used with managed knowledge bases" | Managed KB not selected | [RetrieveAndGenerate API](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_agent-runtime_RetrieveAndGenerate.html) |
| PC-16 | Managed Knowledge Base ACL awareness "is not authorization"; it "cannot verify the authenticity of the user context"; S3 ACL entries use a user email with `Type: USER`; ACL-enabled sources return zero results without `userContext` | Managed KB ACL not selected | [Document-level access controls](https://docs.aws.amazon.com/bedrock/latest/userguide/kb-managed-ds-s3-acl.html) · [ACL-aware retrieval](https://docs.aws.amazon.com/bedrock/latest/userguide/kb-test-retrieve-acl.html) · [Build a managed knowledge base](https://docs.aws.amazon.com/bedrock/latest/userguide/kb-build-managed.html) |
| PC-17 | HTTP API JWT authorizers check the signature via the issuer's `jwks_uri` (RSA algorithms), `kid`, `iss`, `aud` or `client_id`, `exp`, `nbf`, `iat` and route scopes; they deny on failure and pass claims to the integration | CTL-003 | [HTTP API JWT authorizers](https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api-jwt-authorizer.html) |
| PC-18 | "There is no standard mechanism to differentiate JWT access tokens from other types of JWTs"; routes should require authorization scopes | Token-type check in ADR-002 | [HTTP API JWT authorizers](https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api-jwt-authorizer.html) |
| PC-19 | In Cognito user pools, new app clients by default have read and write permission for all standard and custom attributes; custom attributes can be mutable or immutable | Why tenant is not a user attribute | [Working with user attributes](https://docs.aws.amazon.com/cognito/latest/developerguide/user-pool-settings-attributes.html) |
| PC-20 | `cognito:groups` is present in ID and access tokens; the `aws.cognito.signin.user.admin` scope allows users to read and modify their own profile | TS-01 groups as membership | [Pre token generation Lambda trigger](https://docs.aws.amazon.com/cognito/latest/developerguide/user-pool-lambda-pre-token-generation.html) |
| PC-21 | Model invocation logging collects full request and response data; it is disabled by default | CTL-024 | [Model invocation logging](https://docs.aws.amazon.com/bedrock/latest/userguide/model-invocation-logging.html) |
| PC-22 | `Retrieve` and `RetrieveAndGenerate` are CloudTrail **data events** (resource type `AWS::Bedrock::KnowledgeBase`) requiring advanced event selectors, with additional charges; `Converse` and `InvokeModel` are management events | CTL-021; cost note | [Monitor Amazon Bedrock API calls using CloudTrail](https://docs.aws.amazon.com/bedrock/latest/userguide/logging-using-cloudtrail.html) |
| PC-23 | Cross-region inference profiles route requests to regions within a geography, or to any supported commercial region (global) | CTL-023 prohibition | [Cross-Region inference](https://docs.aws.amazon.com/bedrock/latest/userguide/cross-region-inference.html) |
| PC-24 | Model providers do not have access to Amazon Bedrock logs or to customer prompts and completions | Trust placed in the model boundary | [Data protection](https://docs.aws.amazon.com/bedrock/latest/userguide/data-protection.html) |
| PC-25 | Prior art: silo, pool and bridge multi-tenant RAG patterns (AWS Machine Learning Blog, 2024-12-16); two-layer authorisation with retrieval filters built from verified token claims (AWS Architecture Blog, 2026-06-22) | Credibility of the options compared | [Multi-tenant RAG with Amazon Bedrock Knowledge Bases](https://aws.amazon.com/blogs/machine-learning/multi-tenant-rag-with-amazon-bedrock-knowledge-bases/) · [Secure multi-tenant RAG with Amazon Bedrock and Verified Permissions](https://aws.amazon.com/blogs/architecture/secure-multi-tenant-rag-with-amazon-bedrock-and-verified-permissions/) |

## 5. Verify during platform verification

These cannot be settled from documentation alone and must be confirmed before or during the build. None changes a
decision. If one fails, the mapping changes — not the architecture.

| ID | To verify | Why it matters | If it fails |
|---|---|---|---|
| VE-01 | No IAM condition key restricts `Retrieve` or document ingestion by filter or content (re-read the reference table directly) | Confirms exclusivity is the right control | If one exists, add it as defence in depth; CTL-008 stays |
| VE-02 | Quotas in PC-06 for the chosen account and region | Scale and ingestion planning | Adjust inflection points |
| VE-03 | A customer-managed knowledge base with a custom data source, direct ingestion and an S3 Vectors store accepts inline attributes and returns them in `Retrieve` results, with `customDocumentLocation.id` | CTL-011, CTL-017, CTL-018 | Use the ingestion service to write an attribute-verified index through another supported store |
| VE-04 | An `equals` filter on the inline owner attribute is honoured for every query; results never include non-matching chunks | CTL-015 | Stop; revisit the store |
| VE-05 | The API edge passes group claims in a form the resolver can parse unambiguously (single value vs list) | CTL-004 exactly-one rule | Resolver parsing adjusted; test added |
| VE-06 | The chosen embedding and generation models are available **in the contracted region without an inference profile** | CTL-023 | Choose another in-region model or region |
| VE-07 | Function invocation can be restricted so that only the API edge may invoke the services | CTL-009 | Add independent token verification inside the services |
| VE-08 | Administrator-only group membership: users cannot add themselves to groups | CTL-006 | Use another administrator-controlled claim source |
| VE-09 | Whether CloudTrail data events for `Retrieve` include request parameters such as the query text | If they do, those records are content and must be classified accordingly (CTL-020) | Restrict access to the trail; document |
| VE-10 | Deletion through direct ingestion removes the document's vectors, and how long that takes | FUN-003 window | Adjust the window or verification logic |
| VE-11 | A dated cost estimate for a learner build → validate → cleanup session in the chosen region | CON-008 target | Reduce resources or revise the target |

## 6. Educational implementation fit

The free learner implementation uses **the simplest reproducible mechanism that makes the taught control visible and
testable** (the mechanism is chosen in the implementation design). The architecture is not distorted to make the lab easier. **The
production architecture principle is kept; only its implementation is simplified.**

**What stays visible to the learner:**
- the resolver reading tenant only from verified claims;
- the single line that builds the tenant constraint;
- the verification step before generation;
- the audit record showing `constraint_applied` and `retrieved`;
- the negative tests;
- the sensitivity run.

| ID | Production architecture principle | Teaching simplification | Production alternative | Risk accepted in the learner build | Removes the taught control? |
|---|---|---|---|---|---|
| TS-01 | Membership from an authoritative enterprise identity provider; one active tenant per session; explicit switching | Cognito user pool as a stand-in; tenant membership as an administrator-managed group; one tenant per user; no switching | Veltamere's identity provider with its membership model and tenant-switch flow | Multi-tenant user scenarios not exercised | **No** |
| TS-02 | Tenant registry and ownership records as separately governed data | One table with two item types | Separate tables or services with separate write permissions | Coarser permission separation between registry and ownership data | **No** |
| TS-03 | Private networking between services; separate environments and accounts | One sandbox account, one region, public service endpoints | Private endpoints; per-environment accounts | Network-level defence in depth absent | **No** |
| TS-04 | Large-file upload flow with server-fixed object keys | Small synthetic documents sent through the API | Pre-signed uploads to a server-chosen key, then the same consistency gate | Upload size limits | **No** |
| TS-05 | Operator correction tooling with approvals | A documented script run by the operator role | Workflow with approval and dual control | Manual correction steps | **No** |
| TS-06 | Continuous bypass detection alerting on unexpected retrieval callers (CTL-021) | Permission-analysis test (TST-SEC-023) instead of live data-event alarms | Data events + alarm | A bypass created after deployment is not alarmed in the learner build | **No** (primary control unaffected) |
| TS-07 | Audit store with governed retention and restricted access | Separate log group with short sandbox retention | Governed retention agreed with Legal; export to a security account | Short evidence retention | **No** |
| TS-08 | CI/CD with isolation tests on every change | Reproducible scripts run by the learner | Pipeline with isolation and sensitivity stages | Changes are not automatically re-tested | **No** |
| TS-09 | Rate limits and quotas per tenant | None | Episode 04 | Load behaviour untested | **No** |
| TS-10 | Customer-managed encryption keys with restrictive key policies | Provider-managed encryption keys | Customer-managed keys | Less control over key usage | **No** |

## 7. Production pack fit

**The commercial reference implementation is not built here.** The chosen architecture can become a production reference
without changing its decisions. The production concerns it would add:
- **Environment separation:** separate accounts per environment, with identical architecture and configuration-only
  differences.
- **Stronger IAM:** permission boundaries, policy-as-code checks for CTL-008 and CTL-013 exclusivity, drift detection.
- **Production network boundaries:** private endpoints for storage, retrieval and model calls; no public service paths
  except the API edge.
- **Observability:** CTL-021 data-event alarms; audit export to a security account; dashboards for denials and
  `OWNERSHIP_MISMATCH`.
- **Operational controls:** runbooks for tenant onboarding, disablement, attribution correction and exposure
  investigation.
- **Infrastructure as code and automated deployment**, with the isolation suite and the sensitivity run as pipeline
  stages.
- **Security testing:** abuse-case tests, dependency scanning, periodic permission reviews.
- **Scaling:** capacity monitoring against PC-06 limits; the cell evolution (ADR-001).
- **Disaster recovery:** registry, ownership records and originals are authoritative; the retrieval structure is
  **derived** and can be rebuilt from them.
- **Data lifecycle:** retention and offboarding purge (Episode 03).

None of this changes what the free implementation teaches. The free learner sees every decision, alternative, trust
boundary, risk and test in this repository.
