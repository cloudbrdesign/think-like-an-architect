# Run sen3-fresh-20260915-r3-verdict

- Deployment: `None` (variant `None`)
- Started 2026-09-15T10:14:21+00:00 · finished 2026-09-15T10:14:21+00:00
- PASS 1 · FAIL 0 · ERROR 0

| Test | Status | Observed |
|---|---|---|
| `TST-SEN-003` | PASS | baseline PASS → variant FAIL (did not contain it: verification checks chunks against the request's decision, and the decision itself was built from stale claims) → variant destroyed, cleanup verified → restored PASS |
