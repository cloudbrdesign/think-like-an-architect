# Latency summary — E4 fresh-copy run (NFR-001: partially verified)

**What this is:** a coarse summary derived from evidence that already existed. The lab was **not** re-run to produce it.
It describes the educational deployment under the tested conditions. It is **not** a performance benchmark and says
nothing about production latency.

**Tested conditions:**
- one sandbox account in us-east-1;
- functions at default memory (query 512 MB, ingestion 256 MB);
- 7–9 small synthetic documents;
- one harness client making sequential requests over the public internet;
- 2026-09-14, 07:52–08:06 UTC.

## Method

- **What the harness captured:** the time each test result was recorded, at 1-second resolution. Tests run one after
  another, so the interval between one result and the next is the wall time of the later test.
- **Why intervals:** in this run every test's `started_at` was written at the same moment as `finished_at` (a harness
  defect, corrected after the run), so the intervals are the only usable timing.
- **What an interval includes:** the API request or requests; the harness's own reads of the audit record (and, for
  cross-tenant tests, a privileged precondition retrieval); cached token use; and writing the evidence file. It is an
  **upper bound** on request latency.
- **What was lost:** the application measured `latency_ms` inside the function for every request and wrote it to the
  audit record. That field was not included in the harness's evidence view, and the audit table was deleted at cleanup.

## Observations

| Measurement | Samples | Min | Median | Max |
|---|---|---|---|---|
| Successful answered `POST /ask`, end to end including one audit read (TST-ISO-001, TST-ISO-002, TST-SEC-008; TST-SEC-006 = 2 requests in 4 s) | 5 requests in 4 intervals | 2 s | 2 s | 4 s |
| Targeted cross-tenant question: privileged precondition retrieval + `POST /ask` + audit read (TST-ISO-003 and TST-ISO-004 intervals ÷ 6 questions; normal, baseline and bracketing runs) | 24 questions in 4 intervals | 2.8 s | 2.8 s | 3.2 s |
| Same, against the sensitivity variant, where every response was withheld before generation | 6 questions in 1 interval | 2.8 s | — | — |

Supporting timings from the same run:
- **Deployment:** `tla-s01e01-normal` created in 101 s.
- **Fixtures:** 7 documents uploaded and indexed serially in 94 s.
- **Full session:** preflight to verified cleanup took 18 min 8 s (see `FRESH_COPY_RUN.md`).

## What this demonstrates

- In the tested setup, a learner's question returns an answer in a few seconds, end to end, including generation.
- The isolation controls do not add a delay a learner would notice: the registry check, the constrained retrieval,
  ownership verification and the audit write all fit inside those few seconds.
- Withheld responses (no generation) were not measurably faster at this resolution. The coarse data does not
  support any claim about how much each step contributes.

## What this does not demonstrate

- **No component breakdown** (registry read, retrieval, ownership verification, generation). It was not captured.
- **No percentiles.** The sample is far too small, and the resolution is 1 second.
- **No cold-start versus warm behaviour, concurrency, sustained load, larger corpora or other regions.**
- **No production performance.** Production latency needs its own measurement (Cost and Scale Analysis).

## Verification status and the correction for future runs

NFR-001 is **PARTIALLY VERIFIED**. Latency was measured and is reported here for end-to-end behaviour, but not
per component.

The harness now records every request's client-observed time (`client_elapsed_ms`) and the function's own `latency_ms`
from the audit record in each evidence file, with correct test start times. A learner's future run therefore produces
the per-request measurements this summary lacks.
