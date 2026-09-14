# Cost and Scale Analysis — Veltamere Document Assistant

**Stage:** architecture (E2) · **Status:** accepted — architecture approved 2026-09-14 · **Date:** 2026-09-14

This is **architectural reasoning about cost structure**, not a pricing spreadsheet. It contains **no prices**. A dated
cost estimate for the learner implementation, with its region and assumptions, is produced at build authorisation (VE-11)
before anything is deployed.

## 1. Cost structure of the isolation options

| Structure | A — dedicated per tenant | B — shared, enforced partition (chosen) | C — cells | D — per-user access lists |
|---|---|---|---|---|
| Fixed cost per tenant | Any minimum cost of an index, pipeline and monitoring × tenants | None | None (per cell instead) | None |
| Fixed shared cost | Tooling to provision and monitor N structures | One structure's minimum, if any | K cells' minimums | One structure's minimum |
| Variable drivers | Ingestion, storage, queries, generation — per tenant | Ingestion, storage, queries, generation — pooled | Pooled per cell | As B, plus re-indexing on membership change |
| Grows with tenant count? | **Yes, directly** | No — grows with documents and questions | Step-wise with cells | Grows with users × documents |
| Operational cost (people) | Highest | Lowest | Medium | Medium |

## 2. Cost drivers of the chosen design

| Driver | Fixed or variable | Per tenant or shared | Grows with | Architectural note |
|---|---|---|---|---|
| Document ingestion (parsing, chunking, embedding) | Variable | Shared | Documents uploaded and re-ingested | Corrections re-ingest (ADR-004) |
| Storage of originals | Variable | Shared | Document volume | ASM-002 skew: a few large tenants dominate |
| Vector and attribute storage | Variable | Shared | Chunks = documents × average chunks per document | Owner and document identifier attributes are small (PC-10) |
| Retrieval queries | Variable | Shared | Questions | One retrieval per question |
| Registry and ownership reads | Variable | Shared | Questions × (1 + results verified) | CTL-005, CTL-017 |
| Generation | Variable | Shared | Questions × context size × answer length | Expected to be a significant variable driver; confirm in the dated estimate |
| API edge and function invocations | Variable | Shared | Requests | — |
| Security audit records and logs | Variable | Shared | Requests × record size; retention period | Content-free records are small |
| Platform data events for bypass detection | Variable | Shared | Retrieval and ingestion calls | Additional charges (PC-22); production only in the learner build (TS-06) |
| Encryption key usage | Fixed + variable | Shared | Keys and requests | Customer-managed keys in production (TS-10) |

**What does not grow with tenant count:** no structure, pipeline, key or alarm is created per tenant. Onboarding adds a
registry entry and identity-provider membership (NFR-002, NFR-004).

## 3. Scale against the approved assumptions

| Assumption | What it means for the chosen design |
|---|---|
| ASM-001 — about 120 tenants, towards 400 | No per-tenant resources; tenant count affects only registry size and audit volume |
| ASM-002 — a few hundred to about 50,000 documents per tenant | Shared structure size is dominated by the largest tenants. Large tenants affect ingestion throughput for everyone (single ingestion job per structure, PC-06) and make each tenant's constraint more selective |
| ASM-003 — a few thousand questions a day, peak about 15 per minute, about three times that in two years | 15 per minute ≈ 0.25 retrievals per second; three times ≈ 0.75 per second. Each question costs one registry read, one retrieval, one batched ownership read, one generation call and one audit record |

## 4. Where the chosen architecture stops being attractive

| Inflection point | Signal | Response |
|---|---|---|
| Contracts demand physical separation or per-tenant keys for more than a few tenants | Sales and legal requirements | Move those tenants to dedicated cells (ADR-001 evolution); keep the tenant constraint |
| Ingestion contention | Upload-to-available time rises for small tenants when a large tenant ingests | Queue ingestion with fairness; place large tenants in their own cell |
| Query rate approaches platform limits | The documented retrieval rate limit is 20 per second per account and region, stated as not adjustable (PC-06) — roughly 25 times the projected two-year peak | Several structures or accounts; re-evaluate the store |
| Query pattern no longer "infrequent" | The chosen vector store is documented as best suited to infrequent query workloads (PC-10); latency or cost measured in the pilot drifts from NFR-001 or NFR-004 | Move to a store designed for sustained query volume (for example the OpenSearch evolution in the service mapping) |
| Generation cost per question exceeds what a subscription tier can absorb | Cost per active tenant against price | Episode 05 (cost optimisation) |
| Retrieval quality falls for very selective tenant constraints in a very large shared structure | Pilot relevance measurements for small tenants | Cells by size |
| Audit and data-event volume cost | Monitoring spend | Sampling for operational logs only — **never** for security audit records |

## 5. Learner implementation — cost drivers and cleanup plan

The learner build is **not** priced here. At build authorisation, a dated estimate (VE-11) must confirm the CON-008 target
(a complete build → validate → cleanup session under USD 10 — **TARGET**).

**Planned billable resources (confirmed at E3):**
- identity-provider user pool;
- API edge;
- two functions;
- registry/ownership table;
- document bucket;
- knowledge base with vector index;
- embedding and generation model usage;
- log groups;
- encryption keys, if customer-managed.

**Cost drivers to keep small:** number and size of synthetic documents (ingestion and embedding), number of test
questions (generation), log retention, and leaving anything running after validation.

**Cleanup plan (outline):**
1. Delete indexed documents and the knowledge base.
2. Delete the vector index and vector bucket.
3. Empty and delete the document bucket.
4. Delete functions, the API, the table, log groups and the user pool.
5. Schedule key deletion if customer-managed keys were created.
6. **Verify** by searching for any remaining resource carrying the episode's tag (TST-OPS-012). A clean result lists no
   resources.

The sensitivity variant (TST-SEN-011) is deployed as a separate, tagged stack and is destroyed immediately after its run.
