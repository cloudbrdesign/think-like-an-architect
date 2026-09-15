# Fresh-copy run — attempt 1 (interrupted)

The local runner process was stopped by the operating system for low memory on the operator's machine during
TST-SEC-005, after 23 of the 27 suite tests had been recorded (23 PASS, 0 FAIL, 0 ERROR). It is **not** a test
result. The deployment was destroyed and cleanup verified (`fresh-20260915-attempt1-cleanup`); no fault policy was
left attached. The run was repeated from a new clean clone as attempt 2.

## Recorded steps

- `fresh clone of the pre-publication source; tracked changes: 0`
- `unit tests exit 0`
- `oracle tests exit 0`
- `[preflight] exit 0`
- `[build normal] exit 0`
- `[deploy normal] exit 0`
- `[fixtures load] exit 0`
- `PASS   TST-ELG-001    outcome ANSWERED; retrieved ['D-01-S1', 'D-01-S2', 'D-02-S1', 'D-04-S1', 'D-12-S1']; cited ['D-01-S1', 'D-01-S2', 'D-02-S1', 'D-04-S1', 'D-12-S1']`
- `PASS   TST-ELG-002    outcome ANSWERED; retrieved ['D-03-S1', 'D-03-S2', 'D-03-S3', 'D-03-S4', 'D-14-S1']; cited ['D-03-S1', 'D-03-S2', 'D-03-S3', 'D-03-S4', 'D-14-S1']`
- `PASS   TST-ELG-003    precondition: P-02 retrieved D-03 §4 immediately before; no ineligible canary for 6 personas × 2 questions`
- `PASS   TST-ELG-004    lessons retrieved+cited: True; D-03 §4 retrieved in: []; leaks []`
- `PASS   TST-ELG-005    precondition: P-04 retrieved D-07; no SEC-SIGNALLING canary for P-03`
- `PASS   TST-ELG-006    preconditions: P-05 and P-06 retrieved their cases; leaks []; restricted tier called for P-07 in []`
- `PASS   TST-ELG-007    own case retrieved+cited {'P-05 SI-0417': True, 'P-06 HR-2031': True}; leaks []`
- `PASS   TST-ELG-008    identical: True; both uniform: True; outcomes NO_RELEVANT_CONTENT / NO_RELEVANT_CONTENT; leaks []`
- `PASS   TST-ELG-009    P-05 restricted tier searched: True; P-02 shared tier searched: True; leaks []`
- `PASS   TST-SEC-002    token groups ['case.HR-2031', 'domain.BID-ORION']; decision domains [] cases [] = store []/[] v1: True; tiers ['shared']; leaks []`
- `PASS   TST-SEC-003    constraint hashes identical to baseline: True; D-12 (injected text) retrieved: True; leaks []`
- `PASS   TST-SEC-006    4/4 refused with zero tier calls and the uniform response`
- `PASS   TST-DATA-001   quarantine ['LABEL_MISSING']; absent from both tiers: True; P-01 retrieved ['D-01-S1', 'D-02-S1', 'D-02-S2', 'D-04-S1', 'D-13-S1']`
- `PASS   TST-DATA-002   {'D-10': {'reasons': ['LABEL_INVALID'], 'absent': True, 'ok': True}, 'D-11': {'reasons': ['SCOPE_MISSING'], 'absent': True, 'ok': True}, 'D-15': {'rea`
- `PASS   TST-DATA-003   D-14 chunks [('CONFIDENTIAL', 'BID-ORION', 'shared')]; P-01 retrieved D-14: False; P-02 retrieved D-14: True`
- `PASS   TST-DATA-004   excluded at ingestion ['D-04-S3']; chunks 0; section objects []; retrieved/answered for []; audit hits False; log hits {}`
- `PASS   TST-DATA-005   17 chunks checked; problems: []`
- `PASS   TST-DATA-006   problems: []; cache resources []; cache settings []`
- `PASS   TST-SCALE-001  P-10 retrieved D-08: True, leaks [], constraint [926] bytes, decision 5 ms; P-11 outcome REFUSED_CONSTRAINT_INCOMPLETE, tiers []; largest application-`
- `PASS   TST-SEC-004    every capability held only by its intended principal; direct invocation denied (AccessDeniedException)`
- `PASS   TST-CHG-001    same token: True (groups claim ['domain.BID-ORION']); before retrieved D-03 §4: True; after revocation retrieved BID-ORION: []; decision domains [] gr`
- `PASS   TST-SEC-007    wrong-label chunk retrieved: True; outcome WITHHELD_VERIFICATION_MISMATCH; mismatches [{'chunk_id': 'bc433406-0a28-495a-8237-00ebf87859e8', 'reason':`
- `PASS   TST-CHG-002    before: D-13 retrieved True; after reclassification: [('P-01', 'WITHHELD_VERIFICATION_MISMATCH'), ('P-07', 'WITHHELD_VERIFICATION_MISMATCH')]; after r`
