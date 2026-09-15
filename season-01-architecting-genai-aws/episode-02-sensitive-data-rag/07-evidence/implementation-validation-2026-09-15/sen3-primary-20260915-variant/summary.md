# Run sen3-primary-20260915-variant

- Deployment: `tla-s01e02-sen-claims` (variant `claims-as-grants`)
- Started 2026-09-15T07:15:36+00:00 · finished 2026-09-15T07:15:52+00:00
- PASS 0 · FAIL 1 · ERROR 0

| Test | Status | Observed |
|---|---|---|
| `TST-CHG-001` | FAIL | same token: True (groups claim ['domain.BID-ORION']); before retrieved D-03 §4: True; after revocation retrieved BID-ORION: ['D-03-S4', 'D-14-S1']; decision domains ['BID-ORION'] grants_version 2 (revoked version 2) |
