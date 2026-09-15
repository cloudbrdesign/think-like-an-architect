# Fresh-copy run — attempt 2 (interrupted)

Clean clone of the committed internal revision (zero tracked changes). Unit and oracle tests, preflight, build, deploy,
fixtures, the full validation suite (27 PASS · 0 FAIL · 0 ERROR) and experiment 1 (TST-SEN-001 PASS) completed. During
experiment 2's variant target tests — which were failing as predicted — the local runner process was stopped by the
operating system for low memory on the operator's machine. **Not a test result.** Both remaining deployments (the
labels-corrupted variant and the normal deployment) were destroyed and cleanup verified
(`fresh-20260915-r2-interrupted-cleanup`). The harness was changed to run each step in its own short process and the run
was repeated from a new clean clone as attempt 3.

## Recorded steps

- `fresh clone of the pre-publication source; tracked changes: 0`
- `unit tests exit 0`
- `oracle tests exit 0`
- `[preflight] exit 0`
- `[build normal] exit 0`
- `[deploy normal] exit 0`
- `[fixtures load] exit 0`
- `run fresh-20260915-r2-normal-all: PASS 27 · FAIL 0 · ERROR 0`
- `[validation suite] exit 0`
- `run sen1-fresh-20260915-r2-baseline: PASS 4 · FAIL 0 · ERROR 0`
- `run sen1-fresh-20260915-r2-variant: PASS 0 · FAIL 4 · ERROR 0`
- `run sen1-fresh-20260915-r2-cleanup: PASS 1 · FAIL 0 · ERROR 0`
- `run sen1-fresh-20260915-r2-restored: PASS 4 · FAIL 0 · ERROR 0`
- `PASS   TST-SEN-001    baseline PASS → variant FAIL (DETECTED AND CONTAINED every leaked request before generation) → variant destroyed, cleanup verified → restored PASS`
- `run sen1-fresh-20260915-r2-verdict: PASS 1 · FAIL 0 · ERROR 0`
- `[experiment 1] exit 0`
- `run sen2-fresh-20260915-r2-baseline: PASS 3 · FAIL 0 · ERROR 0`
