# Fresh-copy reproducibility run (TST-OPS-018)

**Source:** a clean `git clone` of branch `episode-01/educational-implementation` at commit `3af258e9b7a8bdde9b9aef9c33655c392aaca723`, with no
tracked changes. The only local file created was `config/learner.env`, from the example, for the sandbox account,
region, deployment role path and permissions boundary. It contains no secrets and is git-ignored.

**Mode:** steps 0–6 of the learner guide, non-interactive, run by a driver script that records each step's UTC
start, end and exit code. Cleanup always runs, even after a failure.

## Attempt 1 — deployment defect found and fixed

| Step | Started (UTC) | Finished (UTC) | Exit |
|---|---|---|---|
| 0 preflight | 2026-09-14T07:47:24Z | 2026-09-14T07:47:32Z | 0 |
| 1 build | 2026-09-14T07:47:32Z | 2026-09-14T07:47:32Z | 0 |
| 2 deploy | 2026-09-14T07:47:32Z | 2026-09-14T07:47:37Z | 1 |
| 6a cleanup | 2026-09-14T07:47:37Z | 2026-09-14T07:47:52Z | 0 |
| 6b verify-cleanup | 2026-09-14T07:47:52Z | 2026-09-14T07:48:12Z | 0 |

Step 2 failed: the artifact bucket had been deleted by the previous cleanup minutes earlier, and S3 briefly
answered `NoSuchBucket` to `PutPublicAccessBlock` right after re-creating it. Cleanup still ran and verified CLEAN.
The deploy script now retries only those transient errors, with a bound, and has component tests for it.

## Attempt 2 — commit `3af258e9b7a8bdde9b9aef9c33655c392aaca723`

| Step | Started (UTC) | Finished (UTC) | Exit |
|---|---|---|---|
| 0 preflight | 2026-09-14T07:49:26Z | 2026-09-14T07:49:35Z | 0 |
| 1 build | 2026-09-14T07:49:35Z | 2026-09-14T07:49:36Z | 0 |
| 2 deploy | 2026-09-14T07:49:36Z | 2026-09-14T07:51:17Z | 0 |
| 3 fixtures | 2026-09-14T07:51:17Z | 2026-09-14T07:52:51Z | 0 |
| 4 run all | 2026-09-14T07:52:51Z | 2026-09-14T07:58:56Z | 0 |
| 5 sensitivity | 2026-09-14T07:58:56Z | 2026-09-14T08:05:54Z | 0 |
| 6 evidence bundle | 2026-09-14T08:05:54Z | 2026-09-14T08:05:54Z | 0 |
| 6a cleanup | 2026-09-14T08:05:54Z | 2026-09-14T08:07:10Z | 0 |
| 6b verify-cleanup | 2026-09-14T08:07:10Z | 2026-09-14T08:07:34Z | 0 |

Exit code 1 from `run --suite all` or from the sensitivity variant's own run would mean a FAIL. The
sensitivity script's variant run is *expected* to FAIL; its verdict is recorded separately. See the result
folders next to this file.
