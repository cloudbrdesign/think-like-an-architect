<!-- template: tla-cost-and-cleanup/1 -->
# Cost and Cleanup — Veltamere Document Assistant

**Stage:** build authorisation and implementation design (E3) · **Date of estimate:** 2026-09-14 · **Region:** US East
(N. Virginia), `us-east-1`

**Read this before deploying anything.** The learner implementation creates resources in **your own** sandbox AWS
account, and they are billable.

## Before you start

- Use a **dedicated sandbox account** (see [PLATFORM_VERIFICATION section 1](PLATFORM_VERIFICATION.md#1-learner-sandbox-requirements-pd-09)).
- Create an AWS Budgets monthly budget with alerts at 50%, 80% and 100%. A ceiling of USD 20 is suggested.
- Deploy in `us-east-1`. The design requires In-Region models (CTL-023), and costs and availability differ by region.
- Plan to deploy, validate and clean up **in the same session**.

## Billable resources

| Resource | Billing model | Persists after cleanup? |
|---|---|---|
| Amazon Bedrock — Titan Text Embeddings V2 (embedding at ingestion and query) | Per token | No — usage only |
| Amazon Bedrock — Amazon Nova Micro (generation) | Per input and output token | No — usage only |
| Bedrock knowledge base (customer-managed) and custom data source | No knowledge-base-specific charge was found for customer-managed knowledge bases on the pricing page read (the charges shown there are for managed knowledge bases) — **NOT VERIFIED**, see the pessimistic line below | No — deleted with the stack |
| Amazon S3 Vectors — vector bucket and index | Storage per GB-month; PUT per GB (minimum 128 KB per PUT); per query; data processed and returned | No — deleted with the stack (the bucket must be empty; the index is deleted first) |
| Amazon S3 — document bucket and artifact bucket | Storage per GB-month; per request | No — emptied and deleted by the cleanup script |
| AWS Lambda — two functions | Per request and per GB-second | No — deleted with the stack |
| Amazon API Gateway — HTTP API | Per request | No — deleted with the stack |
| Amazon DynamoDB — two on-demand tables | Per read and write request unit; storage | No — deleted with the stack |
| Amazon CloudWatch Logs — three log groups (1-day retention) | Per GB ingested; storage | No — defined in the stack and deleted with it |
| Amazon Cognito — user pool (Lite tier) | Per monthly active user above the free tier | No — deleted with the stack |
| AWS KMS | No customer-managed keys are created (TS-10); default encryption is used | — |

**Not created at all:** CloudTrail data events, model invocation logging, NAT gateways, VPC endpoints, OpenSearch
collections — nothing is billed by the hour.

## Cost drivers

- **Model usage:** the number of questions × context size (5 retrieved chunks) × answer length. The biggest variable
  driver.
- **Function duration:** the query function waits for retrieval and generation.
- **Ingestion volume:** the number and size of documents, and how often they are re-ingested.
- **Forgetting cleanup:** storage persists — small. A deployed, reachable API remains until deleted.

## Estimated cost (dated 2026-09-14)

**How the estimate was made:**
- Public AWS pricing pages for US East (N. Virginia), read on 2026-09-14 (PE-15), using summarised page reads.
- The Titan Text Embeddings V2 price comes from a secondary AWS source and is to be confirmed on the pricing page.
- Free tiers are **excluded** from the totals, because many learners' free tiers are already used or expired.
- Tax is excluded. Prices change: re-check before relying on them.

**Session assumptions** (deliberately generous):

| Assumption | Value |
|---|---|
| Deployment lifetime | ≤ 3 hours normal stack; ≤ 30 minutes sensitivity stack |
| Corpus | 11 synthetic Markdown documents (≈ 2,000 tokens each); sensitivity stack re-ingests 7 |
| Embedding tokens (ingestion + queries) | ≤ 0.1 million |
| Model calls | ≤ 150, each ≈ 3,000 input and ≈ 400 output tokens → ≤ 0.45 M input, ≤ 0.06 M output tokens |
| Vectors | ≤ 300 vectors, ≤ 7 KB each; ≤ 300 PUT operations, each billed at the 128 KB minimum |
| Vector queries | ≤ 600 |
| API requests / function invocations | ≤ 2,000 each; average ≤ 6 s at ≤ 512 MB → ≤ 6,000 GB-seconds |
| DynamoDB | ≤ 20,000 read and ≤ 10,000 write request units |
| Logs ingested | ≤ 50 MB |
| Cognito | ≤ 6 monthly active users |

**Estimate:**

| Item | Price used (US East, 2026-09-14) | Calculation | Approximate cost |
|---|---|---|---|
| Nova Micro generation | USD 0.08 / M input tokens; USD 0.24 / M output tokens | 0.45 × 0.08 + 0.06 × 0.24 | USD 0.05 |
| Titan Text Embeddings V2 | USD 0.02 / M tokens (secondary source) | 0.1 × 0.02 | < USD 0.01 |
| S3 Vectors PUT | USD 0.20 / GB, 128 KB minimum per PUT | 300 × 128 KB ≈ 0.038 GB | < USD 0.01 |
| S3 Vectors storage, queries, data | USD 0.06 / GB-month; USD 2.50 / M queries | ≈ 2 MB for hours; 600 queries | < USD 0.01 |
| Lambda | USD 0.20 / M requests; USD 0.0000166667 / GB-second | 2,000 requests; 6,000 GB-s | USD 0.10 |
| API Gateway HTTP API | USD 1.00 / M requests | 2,000 requests | < USD 0.01 |
| DynamoDB on-demand | USD 0.125 / M reads; USD 0.625 / M writes | 20,000 + 10,000 | < USD 0.01 |
| CloudWatch Logs | USD 0.50 / GB ingested | 0.05 GB | USD 0.03 |
| S3 standard storage and requests | per GB-month and per 1,000 requests | ≈ 2 MB; ≤ 1,000 requests | < USD 0.01 |
| Cognito Lite | Free tier documented as not time-limited | ≤ 6 MAU | USD 0 (if the free tier applies) |
| **Expected total** | | | **≈ USD 0.20** |
| Pessimistic line — if customer-managed `Retrieve` were billed like managed knowledge bases | USD 1.00 / 1,000 calls (managed knowledge-base price) | 600 calls | + USD 0.60 |
| **Pessimistic total** | | | **≈ USD 0.80** |
| **Heavy exploration** (5× model, request and function usage on top of the pessimistic total) | | | **≈ USD 1–4** |

**CON-008 (under USD 10 per session): plausible with a wide margin.** It is confirmed only when the first real run's
bill is read (VE-11) — billing data can lag by a day.

### Fixed / minimum cost

- No resource is billed per hour.
- The only minimum-charge rule identified is S3 Vectors' 128 KB minimum per PUT.
- Cognito Lite has a free tier of monthly active users.

### Variable cost

Everything else: tokens, requests, function time, vector operations, log ingestion.

### Cost if cleanup is missed

Idle storage costs **cents per month or less**: a few megabytes in S3 and S3 Vectors, small DynamoDB tables and 1-day
logs. The real risks of a missed cleanup are not cost:
- a reachable API and a user pool with test users remain (authenticated access only);
- a forgotten sensitivity deployment would keep a deliberately broken retrieval path alive.

Whether requests rejected by the authorizer are billed is **NOT VERIFIED**.

## Cleanup design

Every billable resource has an owner, a deletion method, dependencies and a verification.

| Resource | Created by | Deletion method | Dependencies | Cleanup verification |
|---|---|---|---|---|
| Sensitivity stack (all resources below, variant `sensitivity`) | `sensitivity-run.sh` | Deleted by `sensitivity-run.sh` at the end of the run; `cleanup.sh` deletes it first if still present | Its document bucket emptied first | No stack named `tla-s01e01-sensitivity-*`; no resource tagged `tla:variant=sensitivity` |
| Document bucket objects | Ingestion function | `cleanup.sh` deletes every object | Before stack deletion | Bucket gone with stack |
| Stack `tla-s01e01-<suffix>` | `deploy.sh` | `cleanup.sh`: delete stack and wait | Bucket empty; no sensitivity stack | Stack `DELETE_COMPLETE` or not found |
| — Knowledge base + custom data source (deletion policy `DELETE`) | Stack | Stack deletion | Before index | No knowledge base named `tla-s01e01-*` |
| — Vector index, then vector bucket | Stack | Stack deletion (bucket must be empty — PE-07; confirmed by SPK-I) | After knowledge base | No vector bucket named `tla-s01e01-*` |
| — Functions, their log groups, API + access log group | Stack | Stack deletion (log groups declared in the stack; functions log only to them) | — | No functions or log groups with the episode prefix |
| — DynamoDB tables (registry, audit) | Stack | Stack deletion | Export evidence first | No tables with the episode prefix |
| — Cognito user pool (users and groups created by the fixture loader) | Stack (pool); harness (users) | Stack deletion removes users and groups | — | No user pool with the episode name |
| — IAM roles | Stack | Stack deletion | After functions and knowledge base | No roles under path `/tla/s01e01/` |
| Artifact bucket | `deploy.sh` | `cleanup.sh`: empty, then delete | After stack deletion | Bucket not found |
| Local harness results | Harness | Kept by the learner as evidence (not billable) | Redact before sharing | — |

## Cleanup (the single documented flow)

1. **Keep your evidence:** `python -m harness evidence bundle`. The audit table is deleted in the next step.
2. **Run** `scripts/cleanup.sh`. It:
   - deletes any sensitivity stack;
   - empties the document bucket;
   - deletes the stack and waits;
   - empties and deletes the artifact bucket;
   - prints what it removed.
3. **Verify:** `python -m harness verify-cleanup` (TST-OPS-012).

## Verify cleanup

`verify-cleanup` checks, and records in the results file:
1. A tag search for `tla:episode=s01e01` returns **no** resources.
2. Named checks, because tag search does not cover every resource type:
   - no stack with the episode prefix;
   - no knowledge base, vector bucket, function, table, user pool, API, IAM role (path `/tla/s01e01/`) or log group
     with the episode prefix;
   - the artifact bucket is not found.
3. It reports **CLEAN** only if every check is empty. Otherwise it lists each remaining resource and the command that
   removes it.

## What changes at production scale

Veltamere's production costs follow the E2 [cost and scale analysis](../03-architecture/COST_AND_SCALE_ANALYSIS.md).
- Generation and function time grow with questions.
- Vector storage grows with documents.
- Audit records and data events grow with requests.

Customer-managed keys, private networking, bypass alerting and longer retention add costs that the learner build
deliberately omits.
