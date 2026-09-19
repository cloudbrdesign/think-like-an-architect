<!-- template: tla-cost-and-cleanup/1 -->
# Cost and Cleanup — keeping the knowledge base current

**Stage:** implementation · **Date of estimate:** 2026-09-16 · **Region:** US East (N. Virginia), `us-east-1`

**Read this before deploying anything.** The learner implementation creates billable resources in **your own** sandbox
AWS account.

**Where the prices come from:** the dated figures read on 2026-09-14 for the Episode 01 estimate (public AWS pricing
pages, US East), reused here. They were **not re-read for this episode** — re-check them before relying on them. Free
tiers and tax are excluded.

## Before you start

- Use a dedicated sandbox account. Synthetic data only; never point this at real records.
- Create a monthly AWS Budget with alerts at 50/80/100% (USD 20 suggested) and put its name in
  `config/learner.env` as `TLA_BUDGET_NAME`; preflight checks that it is readable.
- Deploy in `us-east-1` (In-Region models).
- Deploy, validate and clean up **in one session**. Nothing here is meant to stay running.

## What Episode 03 adds to Episode 02's deployment

| Added resource | Why the architecture needs it | Billing model |
|---|---|---|
| DynamoDB stream on the records table | The change signal comes from the authority itself, so a change made by hand still produces one (ADR-003) | Stream read requests |
| Lambda — change notifier | Writes a pending entry before content work starts | Requests and GB-seconds |
| Lambda — change applier | The single writer of derived retrieval state (ADR-004) | Requests and GB-seconds |
| Lambda — reconciler | The only mechanism that may establish completeness (ADR-003) | Requests and GB-seconds |
| Lambda — rebuild | The exceptional repair path (ADR-008) | Requests and GB-seconds |
| DynamoDB table — convergence state | Pending set, reflected versions, generations, watermarks, reconciliation passes, deletion ledger | On-demand reads and writes; a few hundred small items |
| Event source mapping (stream → notifier) | Delivery, and FX-3's honest off switch | No separate charge |
| Four more CloudWatch log groups (1-day retention) | Observability of the change path | Per GB ingested |

Episode 02's resources are otherwise unchanged: two knowledge bases on S3 Vectors, Titan embeddings, Nova Micro,
Cognito, the HTTP API, the records and section buckets, and the authorization and audit tables.

**Not created:** model invocation logging, CloudTrail data events, API caching, NAT gateways, VPC endpoints, OpenSearch,
customer-managed KMS keys, schedules. Nothing is billed by the hour.

## Session assumptions (deliberately generous)

The session covers the normal deployment plus three short-lived experiment deployments, one at a time.

| Assumption | Value |
|---|---|
| Deployments | Normal ≤ 4 hours; each variant ≤ 45 minutes |
| Corpus | 15 synthetic documents, about 22 sections. **Educational scale (§17)** — never the fictional client's 180,000 documents |
| Change activity | ≈ 60 authoritative changes across the run (supersede, withdraw, new version, reclassify, delete, replay, rebuild) |
| Generations built | ≈ 120 (each change rebuilds one document's sections; rebuild rebuilds all of them once) |
| Embedding tokens | ≤ 0.4 million (generations are re-embedded on each build) |
| Model calls | ≤ 300 × (≈ 3,000 input + ≈ 400 output tokens) |
| Vector PUTs / queries | ≤ 900 PUTs (128 KB minimum each) / ≤ 2,000 queries |
| API requests / function invocations | ≤ 5,000; ≤ 15,000 GB-seconds |
| DynamoDB | ≤ 60,000 reads, ≤ 30,000 writes (convergence state is read once per request and written once per change) |
| Logs ingested | ≤ 150 MB |

## Estimate (dated 2026-09-14 prices)

| Item | Price used | Calculation | Approximate cost |
|---|---|---|---|
| Nova Micro | USD 0.08 / M input; USD 0.24 / M output | 0.9 × 0.08 + 0.12 × 0.24 | USD 0.10 |
| Titan Text Embeddings V2 | USD 0.02 / M tokens | 0.4 × 0.02 | < USD 0.01 |
| S3 Vectors PUT | USD 0.20 / GB, 128 KB minimum | 900 × 128 KB ≈ 0.11 GB | USD 0.02 |
| S3 Vectors storage and queries | USD 0.06 / GB-month; USD 2.50 / M queries | a few MB for hours; 2,000 queries | USD 0.01 |
| Lambda | USD 0.20 / M requests; USD 0.0000166667 / GB-second | 5,000 requests; 15,000 GB-s | USD 0.25 |
| API Gateway HTTP API | USD 1.00 / M requests | 5,000 | USD 0.01 |
| DynamoDB on-demand (incl. stream reads) | USD 0.125 / M reads; USD 0.625 / M writes | 60,000 + 30,000 | USD 0.03 |
| CloudWatch Logs | USD 0.50 / GB | 0.15 GB | USD 0.08 |
| S3 storage and requests | per GB-month; per 1,000 requests | a few MB; ≤ 4,000 requests | < USD 0.01 |
| Cognito Lite | free tier documented as not time-limited | ≤ 11 MAU | USD 0 if the free tier applies |
| **Expected total** | | | **≈ USD 0.50** |
| Pessimistic line — if customer-managed `Retrieve` were billed like managed knowledge bases | USD 1.00 / 1,000 calls | 2,000 calls | + USD 2.00 |
| **Pessimistic total** | | | **≈ USD 2.50** |
| **Heavy exploration** (5× model, request and function usage) | | | **≈ USD 3–8** |

**Confirmation:** an estimate is confirmed only by the bill, which lags by about a day.

**Observed usage:** none yet. This section is filled from the content-free audit records after the validation run, by
`python3 -m harness export-audit`, and states volumes actually observed — never volumes assumed here.

## Cleanup design

| Resource | Created by | Deletion | Dependencies | Verification |
|---|---|---|---|---|
| Variant stacks `tla-s01e03-fx-*` | Experiment runner | Deleted by the runner immediately after its target tests; `tla_ops.py cleanup` deletes any that remain **first** | Their buckets emptied first | No stack named `tla-s01e03-fx-*` |
| Event source mapping (records stream → notifier) | Stack | Stack deletion | Before the function | No mapping whose function has the prefix |
| Section buckets, records bucket objects | Change applier; fixture loader | `tla_ops.py cleanup` empties them | Before stack deletion | Buckets gone with the stack |
| Stack `tla-s01e03-normal` | `tla_ops.py deploy` | `tla_ops.py cleanup` deletes and waits | Buckets empty; no variant stack | `DELETE_COMPLETE` or not found |
| — Two knowledge bases + custom data sources (deletion policy `DELETE`) | Stack | Stack deletion | Before the indexes | No knowledge base with the prefix |
| — Two vector indexes, then vector buckets | Stack | Stack deletion (index before bucket) | After the knowledge bases | No vector bucket with the prefix |
| — Five functions, five log groups, the API | Stack | Stack deletion | — | None with the prefix |
| — DynamoDB tables (authorization, **records**, **convergence**, audit) | Stack | Stack deletion | **Export evidence first** | No tables with the prefix |
| — Cognito user pool (personas) | Stack; harness | Stack deletion | — | No user pool with the episode name |
| — IAM roles (query, change, notifier, reconciler, two knowledge-base roles) | Stack | Stack deletion | After functions and knowledge bases | No roles named `tla-s01e03-*` |
| Artifact bucket | `tla_ops.py deploy` | `tla_ops.py cleanup` empties, then deletes | After the stacks | Bucket not found |

## Cleanup (the single documented flow)

1. `python3 scripts/tla_ops.py lab-down delivery-off` and `python3 scripts/tla_ops.py lab-down delivery-on` — each
   empties the part's buckets, deletes its stack and package bucket, then checks by name that no stack, knowledge
   base, vector store, bucket, table, function, mapping, log group, user pool or role remains. Safe to repeat.
2. Check the budget the next day.

**Cost if cleanup is missed:** cents per month of storage. The real risks are not cost:

- **Normal deployment:** a reachable API and a user pool of synthetic personas.
- **Variant deployment:** a forgotten variant keeps a **deliberately broken safety path** alive — one that answers from
  superseded documents (FX-1), reinstates older state (FX-2) or claims completeness it has not established (FX-3). That
  is why variants are destroyed immediately after their runs and removed first during cleanup.
