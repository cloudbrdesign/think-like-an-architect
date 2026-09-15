# Run sen1-primary-20260915-baseline

- Deployment: `tla-s01e02-normal` (variant `normal`)
- Started 2026-09-15T06:55:22+00:00 · finished 2026-09-15T06:58:45+00:00
- PASS 3 · FAIL 0 · ERROR 1

| Test | Status | Observed |
|---|---|---|
| `TST-ELG-003` | ERROR | TimeoutError: The read operation timed out |
| `TST-ELG-005` | PASS | precondition: P-04 retrieved D-07; no SEC-SIGNALLING canary for P-03 |
| `TST-ELG-006` | PASS | preconditions: P-05 and P-06 retrieved their cases; leaks []; restricted tier called for P-07 in [] |
| `TST-ELG-009` | PASS | P-05 restricted tier searched: True; P-02 shared tier searched: True; leaks [] |
