<!-- template: tla-cost-and-cleanup/1 -->
# Cost and Cleanup — Kestrelmoor Knowledge Assistant

**Stage:** implementation design · **Date of estimate:** 2026-09-15 · **Region:** US East (N. Virginia), `us-east-1`

**Read this before deploying anything.** The learner implementation creates billable resources in **your own** sandbox
AWS account.

**Where the prices come from:** the prices below are the dated figures read on 2026-09-14 for the Episode 01 estimate
(public AWS pricing pages, US East). They were **not re-read for this gate**; re-check them before relying on them. Free
tiers and tax are excluded.

## Before you start

- Use a dedicated sandbox account.
- Create a monthly AWS Budget with alerts at 50/80/100% (USD 20 suggested).
- Deploy in `us-east-1` (In-Region models).
- Deploy, validate and clean up **in one session**.

## Billable resources

| Resource | Billing model | Persists after cleanup? |
|---|---|---|
| Bedrock — Titan Text Embeddings V2 | Per token | No — usage only |
| Bedrock — Amazon Nova Micro | Per input and output token | No — usage only |
| Two customer-managed knowledge bases (shared, restricted) with custom data sources | No knowledge-base-specific charge identified for customer-managed knowledge bases (**NOT VERIFIED**; see the pessimistic line) | No |
| Amazon S3 Vectors — two vector buckets and indexes | Storage per GB-month; PUT per GB (128 KB minimum per PUT); per query | No — deleted with the stack |
| Amazon S3 — records bucket, two section buckets, artifact bucket | Storage and requests | No — emptied and deleted |
| AWS Lambda — query and ingestion functions | Requests and GB-seconds | No |
| API Gateway HTTP API | Per request | No |
| DynamoDB on-demand — authorization, classification, audit tables | Read and write request units; storage | No |
| CloudWatch Logs (1-day retention) | Per GB ingested | No |
| Amazon Cognito user pool (Lite) | Monthly active users above the free tier | No |

**Not created:** model invocation logging, CloudTrail data events, API caching, NAT gateways, VPC endpoints, OpenSearch,
customer-managed KMS keys. Nothing is billed by the hour.

## Session assumptions (deliberately generous)

The session covers the normal deployment plus three short-lived experiment deployments.

| Assumption | Value |
|---|---|
| Deployments | Normal ≤ 3 hours; each of the three variants ≤ 30 minutes, one at a time |
| Corpus | 15 synthetic documents, about 25 sections, each deployment ingests them once |
| Embedding tokens (ingestion + queries, all deployments) | ≤ 0.2 million |
| Model calls | ≤ 200 × (≈ 3,000 input + ≈ 400 output tokens) → ≤ 0.6 M input, ≤ 0.08 M output |
| Vectors | ≤ 400 PUTs across all deployments, billed at the 128 KB minimum |
| Vector queries | ≤ 1,500 (two tiers for case-assigned personas) |
| API requests / function invocations | ≤ 3,000; average ≤ 6 s at ≤ 512 MB → ≤ 9,000 GB-seconds |
| DynamoDB | ≤ 40,000 reads, ≤ 15,000 writes |
| Logs ingested | ≤ 100 MB |
| Cognito | ≤ 11 monthly active users |

## Estimate (dated)

| Item | Price used (US East, read 2026-09-14) | Calculation | Approximate cost |
|---|---|---|---|
| Nova Micro | USD 0.08 / M input; USD 0.24 / M output | 0.6 × 0.08 + 0.08 × 0.24 | USD 0.07 |
| Titan Text Embeddings V2 | USD 0.02 / M tokens (secondary source) | 0.2 × 0.02 | < USD 0.01 |
| S3 Vectors PUT | USD 0.20 / GB, 128 KB minimum | 400 × 128 KB ≈ 0.05 GB | USD 0.01 |
| S3 Vectors storage and queries | USD 0.06 / GB-month; USD 2.50 / M queries | a few MB for hours; 1,500 queries | < USD 0.01 |
| Lambda | USD 0.20 / M requests; USD 0.0000166667 / GB-second | 3,000 requests; 9,000 GB-s | USD 0.15 |
| API Gateway HTTP API | USD 1.00 / M requests | 3,000 | < USD 0.01 |
| DynamoDB on-demand | USD 0.125 / M reads; USD 0.625 / M writes | 40,000 + 15,000 | USD 0.02 |
| CloudWatch Logs | USD 0.50 / GB | 0.1 GB | USD 0.05 |
| S3 storage and requests | per GB-month and per 1,000 requests | a few MB; ≤ 2,000 requests | < USD 0.01 |
| Cognito Lite | Free tier documented as not time-limited | ≤ 11 MAU | USD 0 if the free tier applies |
| **Expected total** | | | **≈ USD 0.30** |
| Pessimistic line — if customer-managed `Retrieve` were billed like managed knowledge bases | USD 1.00 / 1,000 calls | 1,500 calls | + USD 1.50 |
| **Pessimistic total** | | | **≈ USD 1.80** |
| **Heavy exploration** (5× model, request and function usage on top) | | | **≈ USD 2–6** |

**Confirmation:** the estimate is confirmed only by the first real build run's bill (billing data lags by about a day).

**Verification spike SPK-E02-A (2026-09-15):**
- **Volume:** 12 sections, 42 `Retrieve` calls, one ingestion batch, about 4 minutes of existence.
- **Cost:** well under USD 0.10 by volume. Not yet visible in billing on the day of the run.

**Educational build and validation run (2026-09-15)** — volumes observed from the content-free audit records:

| Deployment | Requests | Knowledge-base searches | Model calls | Input / output tokens | Sections ingested |
|---|---|---|---|---|---|
| Normal (full suite, calibration searches not included) | 306 | 311 | 244 | 75,740 / 7,505 | 44 (three ingestions) |
| Experiment 1 variant (each of two attempts) | 23 | 46 | 0 | — | 17 |
| Experiment 2 variant | 2 | 2 | 0 | — | 17 |
| Experiment 3 variant | 2 | 2 | 2 | 744 / 128 | 17 |

- **Priced with the dated table above:** about USD 0.01 for model tokens, vector queries, embeddings and requests together.
- **Not in that figure:** storage for a few hours, Lambda duration, DynamoDB, CloudWatch Logs, the relevance calibration and
  filter-limit searches (a few hundred operator searches), the fresh-copy repeat of the whole run, and whether
  customer-managed `Retrieve` is billed like managed knowledge bases.
- **Conclusion:** observed usage sits well inside the expected educational range (≈ USD 0.30 per session). The bill is
  the confirmation, and billing data lags by about a day.

## Cleanup design

| Resource | Created by | Deletion | Dependencies | Verification |
|---|---|---|---|---|
| Variant stacks `tla-s01e02-sen-*` | Experiment runner | Deleted by the runner right after its target tests; `cleanup.py` deletes any that remain **first** | Their section and records buckets emptied first | No stack named `tla-s01e02-sen-*`; no resource tagged `Variant≠none` |
| Section buckets (shared, restricted) and records bucket objects | Ingestion; fixture loader | `cleanup.py` empties them | Before stack deletion | Buckets gone with the stack |
| Stack `tla-s01e02-<suffix>` | `deploy.py` | `cleanup.py` deletes and waits | Buckets empty; no variant stack | `DELETE_COMPLETE` or not found |
| — Two knowledge bases + custom data sources (deletion policy `DELETE`) | Stack | Stack deletion | Before indexes | No knowledge base named `tla-s01e02-*` |
| — Two vector indexes, then vector buckets | Stack | Stack deletion (index before bucket) | After knowledge bases | No vector bucket named `tla-s01e02-*` |
| — Functions, log groups, API | Stack | Stack deletion | — | No functions or log groups with the prefix |
| — DynamoDB tables (authorization, classification, audit) | Stack | Stack deletion | **Export evidence first** | No tables with the prefix |
| — Cognito user pool (personas) | Stack; harness | Stack deletion | — | No user pool with the episode name |
| — IAM roles | Stack | Stack deletion | After functions and knowledge bases | No roles named `tla-s01e02-*` |
| Artifact bucket | `deploy.py` | `cleanup.py` empties, then deletes | After stacks | Bucket not found |
| Local evidence bundle | Harness | Kept by the learner | Contains no content by design; synthetic data only | — |

## Cleanup (the single documented flow)

1. `python -m harness evidence bundle` — export the audit records, inventories and reports before tables are deleted.
2. `python scripts/cleanup.py` — deletes any variant stack, empties buckets, deletes the normal stack, deletes the artifact
   bucket.
3. `python -m harness verify-cleanup` — lists stacks, knowledge bases, vector buckets, buckets, tables, functions, log
   groups, user pools and roles with the episode prefix, and fails if any remain.
4. Check your budget the next day.

**Cost if cleanup is missed:** cents per month of storage. The real risks are not cost:
- **Normal deployment:** a reachable API and a user pool with synthetic personas.
- **Variant deployment:** a forgotten variant keeps a **deliberately broken authorization path** alive. That is why
  variants are destroyed immediately after their runs, and cleanup removes variants first.
