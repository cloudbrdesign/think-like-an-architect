# Run primary-20260915-normal-all

- Deployment: `tla-s01e02-normal` (variant `normal`)
- Started 2026-09-15T06:43:55+00:00 · finished 2026-09-15T06:55:18+00:00
- PASS 27 · FAIL 0 · ERROR 0

| Test | Status | Observed |
|---|---|---|
| `TST-CHG-001` | PASS | same token: True (groups claim ['domain.BID-ORION']); before retrieved D-03 §4: True; after revocation retrieved BID-ORION: []; decision domains [] grants_version 2 (revoked version 2) |
| `TST-CHG-002` | PASS | before: D-13 retrieved True; after reclassification: [('P-01', 'WITHHELD_VERIFICATION_MISMATCH'), ('P-07', 'WITHHELD_VERIFICATION_MISMATCH')]; after restore + re-index: ANSWERED |
| `TST-DATA-001` | PASS | quarantine ['LABEL_MISSING']; absent from both tiers: True; P-01 retrieved ['D-01-S1', 'D-02-S1', 'D-02-S2', 'D-04-S1', 'D-13-S1'] |
| `TST-DATA-002` | PASS | {'D-10': {'reasons': ['LABEL_INVALID'], 'absent': True, 'ok': True}, 'D-11': {'reasons': ['SCOPE_MISSING'], 'absent': True, 'ok': True}, 'D-15': {'reasons': ['LABEL_INVALID'], 'absent': True, 'ok': True}}; quarantined se |
| `TST-DATA-003` | PASS | D-14 chunks [('CONFIDENTIAL', 'BID-ORION', 'shared')]; P-01 retrieved D-14: False; P-02 retrieved D-14: True |
| `TST-DATA-004` | PASS | excluded at ingestion ['D-04-S3']; chunks 0; section objects []; retrieved/answered for []; audit hits False; log hits {} |
| `TST-DATA-005` | PASS | 17 chunks checked; problems: [] |
| `TST-DATA-006` | PASS | problems: []; cache resources []; cache settings [] |
| `TST-ELG-001` | PASS | outcome ANSWERED; retrieved ['D-01-S1', 'D-01-S2', 'D-02-S1', 'D-04-S1', 'D-12-S1']; cited ['D-01-S1', 'D-01-S2', 'D-02-S1', 'D-04-S1', 'D-12-S1'] |
| `TST-ELG-002` | PASS | outcome ANSWERED; retrieved ['D-03-S1', 'D-03-S2', 'D-03-S3', 'D-03-S4', 'D-14-S1']; cited ['D-03-S1', 'D-03-S2', 'D-03-S3', 'D-03-S4', 'D-14-S1'] |
| `TST-ELG-003` | PASS | precondition: P-02 retrieved D-03 §4 immediately before; no ineligible canary for 6 personas × 2 questions |
| `TST-ELG-004` | PASS | lessons retrieved+cited: True; D-03 §4 retrieved in: []; leaks [] |
| `TST-ELG-005` | PASS | precondition: P-04 retrieved D-07; no SEC-SIGNALLING canary for P-03 |
| `TST-ELG-006` | PASS | preconditions: P-05 and P-06 retrieved their cases; leaks []; restricted tier called for P-07 in [] |
| `TST-ELG-007` | PASS | own case retrieved+cited {'P-05 SI-0417': True, 'P-06 HR-2031': True}; leaks [] |
| `TST-ELG-008` | PASS | identical: True; both uniform: True; outcomes NO_RELEVANT_CONTENT / NO_RELEVANT_CONTENT; leaks [] |
| `TST-ELG-009` | PASS | P-05 restricted tier searched: True; P-02 shared tier searched: True; leaks [] |
| `TST-OBS-001` | PASS | 252 audit items, 455 log events scanned; canary hits []; question hits 0; log hits {}; model logging enabled False |
| `TST-OBS-002` | PASS | reconstruction checks [{'decision': True, 'constraint_hashes': True, 'verification': True, 'outcome': True}, {'decision': True, 'constraint_hashes': True, 'verification': True, 'outcome': True}, {'decision': True, 'const |
| `TST-SCALE-001` | PASS | P-10 retrieved D-08: True, leaks [], constraint [926] bytes, decision 5 ms; P-11 outcome REFUSED_CONSTRAINT_INCOMPLETE, tiers []; largest application-accepted constraint (445 grants, 8177 bytes) accepted by the service:  |
| `TST-SEC-001` | PASS | statuses {'missing': 401, 'malformed': 401, 'tampered_signature': 401, 'other_application': 401, 'expired': 401}; audit items before 258 after 258 |
| `TST-SEC-002` | PASS | token groups ['domain.BID-ORION', 'case.HR-2031']; decision domains [] cases [] = store []/[] v1: True; tiers ['shared']; leaks [] |
| `TST-SEC-003` | PASS | constraint hashes identical to baseline: True; D-12 (injected text) retrieved: True; leaks [] |
| `TST-SEC-004` | PASS | every capability held only by its intended principal; direct invocation denied (AccessDeniedException) |
| `TST-SEC-005` | PASS | during fault {'P-01': {'outcome': 'REFUSED_AUTHORIZATION_UNAVAILABLE', 'failing_control': 'CTL-004', 'tiers_called': [], 'retrieval': [], 'generation_invoked': False, 'uniform': True}, 'P-02': {'outcome': 'REFUSED_AUTHOR |
| `TST-SEC-006` | PASS | 4/4 refused with zero tier calls and the uniform response |
| `TST-SEC-007` | PASS | wrong-label chunk retrieved: True; outcome WITHHELD_VERIFICATION_MISMATCH; mismatches [{'chunk_id': '4a252927-0f8a-43d2-bd29-018487bc1971', 'reason': 'LABEL_MISMATCH'}]; generation invoked False; after re-ingest D-03 §4  |
