# Latency summary — NFR-001 (primary validation run)

**Source:** the 306 content-free audit records of `primary-20260915-normal-all/audit.jsonl` (per-stage `latency_ms`,
measured inside the query function). Educational deployment, us-east-1, synthetic corpus of 17 indexed sections.

| Stage | Requests with the stage | Median (ms) | 95th percentile (ms) |
|---|---|---|---|
| Authorization decision (fresh consistent reads of HR and grants records) | 306 | 4 | 9 |
| Retrieval (one or two tiers, constraint evaluated during search) | 256 | 366 | 743 |
| Before-generation verification (classification records batch read + checks) | 256 | 4 | 9 |
| Generation (In-Region model) | 244 | 266 | 371 |
| Total inside the function | 306 | 634 | 1,002 |

**What it shows:** reading the authoritative grants on every request and re-checking every chunk before generation
added single-digit milliseconds at the median in this deployment — far inside NFR-001's assumed half-second budget.
Constraint construction is not timed separately; it is in-memory work between the two timed stages.

**What it does not show:** production scale, concurrency, cold starts at scale, larger grant sets than the personas
hold, network time between a client and the API, or a real corpus. It is observed behaviour of this educational
deployment under the tested conditions.
