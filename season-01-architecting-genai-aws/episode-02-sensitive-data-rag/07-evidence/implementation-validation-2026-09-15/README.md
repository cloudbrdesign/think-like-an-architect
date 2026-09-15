# Implementation validation evidence — 2026-09-15

Source: this episode folder as it stood before publication (each fresh-copy run used a clean clone with no local changes) · region us-east-1 · account identifiers redacted · synthetic data only.
Portfolio evidence of the work performed, verified for this educational implementation under the tested conditions — not a certification, a compliance statement or a claim that any system is secure.

| Folder | What it is |
|---|---|
| `primary-20260915-normal-all/` | tests all — PASS 27 · FAIL 0 · ERROR 0 |
| `sen1-primary-20260915-r2-baseline/` | tests TST-ELG-003,TST-ELG-005,TST-ELG-006,TST-ELG-009 — PASS 4 · FAIL 0 · ERROR 0 |
| `sen1-primary-20260915-r2-variant/` | tests TST-ELG-003,TST-ELG-005,TST-ELG-006,TST-ELG-009 — PASS 0 · FAIL 4 · ERROR 0 |
| `sen1-primary-20260915-r2-cleanup/` | cleanup eligibility-removed — PASS 1 · FAIL 0 · ERROR 0 |
| `sen1-primary-20260915-r2-restored/` | tests TST-ELG-003,TST-ELG-005,TST-ELG-006,TST-ELG-009 — PASS 4 · FAIL 0 · ERROR 0 |
| `sen1-primary-20260915-r2-verdict/` | experiment 1 — PASS 1 · FAIL 0 · ERROR 0 |
| `sen2-primary-20260915-baseline/` | tests TST-ELG-004,TST-DATA-005,TST-DATA-006 — PASS 3 · FAIL 0 · ERROR 0 |
| `sen2-primary-20260915-variant/` | tests TST-ELG-004,TST-DATA-005,TST-DATA-006 — PASS 0 · FAIL 3 · ERROR 0 |
| `sen2-primary-20260915-cleanup/` | cleanup labels-corrupted — PASS 1 · FAIL 0 · ERROR 0 |
| `sen2-primary-20260915-restored/` | tests TST-ELG-004,TST-DATA-005,TST-DATA-006 — PASS 3 · FAIL 0 · ERROR 0 |
| `sen2-primary-20260915-verdict/` | experiment 2 — PASS 1 · FAIL 0 · ERROR 0 |
| `sen3-primary-20260915-baseline/` | tests TST-CHG-001 — PASS 1 · FAIL 0 · ERROR 0 |
| `sen3-primary-20260915-variant/` | tests TST-CHG-001 — PASS 0 · FAIL 1 · ERROR 0 |
| `sen3-primary-20260915-cleanup/` | cleanup claims-as-grants — PASS 1 · FAIL 0 · ERROR 0 |
| `sen3-primary-20260915-restored/` | tests TST-CHG-001 — PASS 1 · FAIL 0 · ERROR 0 |
| `sen3-primary-20260915-verdict/` | experiment 3 — PASS 1 · FAIL 0 · ERROR 0 |
| `fresh-20260915-r3-TST-OPS-001/` | fresh-copy run — PASS 1 · FAIL 0 · ERROR 0 |
| `fresh-20260915-r3-normal-all/` | tests all — PASS 27 · FAIL 0 · ERROR 0 |
| `primary-20260915-cleanup-all/` | cleanup — PASS 1 · FAIL 0 · ERROR 0 |
| `fresh-20260915-r3-cleanup-all/` | cleanup — PASS 1 · FAIL 0 · ERROR 0 |
| `sen1-primary-20260915-verdict/` | experiment 1 — PASS 0 · FAIL 1 · ERROR 0 |
| `relevance-calibration/` | relevance calibration — PASS 0 · FAIL 0 · ERROR 0 |
| `filter-limit-measurement/` | platform filter-size re-measurement — PASS 0 · FAIL 0 · ERROR 0 |

## Validation suite — normal deployment (`primary-20260915-normal-all`)

| Test | Status | Key observation |
|---|---|---|
| `TST-CHG-001` | PASS | same token: True (groups claim ['domain.BID-ORION']); before retrieved D-03 §4: True; after revocation retrieved BID-ORION: []; decision domains [] grants_version 2 (revoked version 2) |
| `TST-CHG-002` | PASS | before: D-13 retrieved True; after reclassification: [('P-01', 'WITHHELD_VERIFICATION_MISMATCH'), ('P-07', 'WITHHELD_VERIFICATION_MISMATCH')]; after restore + re-index: ANSWERED |
| `TST-DATA-001` | PASS | quarantine ['LABEL_MISSING']; absent from both tiers: True; P-01 retrieved ['D-01-S1', 'D-02-S1', 'D-02-S2', 'D-04-S1', 'D-13-S1'] |
| `TST-DATA-002` | PASS | {'D-10': {'reasons': ['LABEL_INVALID'], 'absent': True, 'ok': True}, 'D-11': {'reasons': ['SCOPE_MISSING'], 'absent': True, 'ok': True}, 'D-15': {'reasons': ['LABEL_INVALID'], 'absent': True, 'ok': True}}; quarantined sections retrieved: [] |
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
| `TST-OBS-002` | PASS | reconstruction checks [{'decision': True, 'constraint_hashes': True, 'verification': True, 'outcome': True}, {'decision': True, 'constraint_hashes': True, 'verification': True, 'outcome': True}, {'decision': True, 'constraint_hashes': True, 'verification': Tru |
| `TST-SCALE-001` | PASS | P-10 retrieved D-08: True, leaks [], constraint [926] bytes, decision 5 ms; P-11 outcome REFUSED_CONSTRAINT_INCOMPLETE, tiers []; largest application-accepted constraint (445 grants, 8177 bytes) accepted by the service: True, last grant honoured: True; above t |
| `TST-SEC-001` | PASS | statuses {'missing': 401, 'malformed': 401, 'tampered_signature': 401, 'other_application': 401, 'expired': 401}; audit items before 258 after 258 |
| `TST-SEC-002` | PASS | token groups ['domain.BID-ORION', 'case.HR-2031']; decision domains [] cases [] = store []/[] v1: True; tiers ['shared']; leaks [] |
| `TST-SEC-003` | PASS | constraint hashes identical to baseline: True; D-12 (injected text) retrieved: True; leaks [] |
| `TST-SEC-004` | PASS | every capability held only by its intended principal; direct invocation denied (AccessDeniedException) |
| `TST-SEC-005` | PASS | during fault {'P-01': {'outcome': 'REFUSED_AUTHORIZATION_UNAVAILABLE', 'failing_control': 'CTL-004', 'tiers_called': [], 'retrieval': [], 'generation_invoked': False, 'uniform': True}, 'P-02': {'outcome': 'REFUSED_AUTHORIZATION_UNAVAILABLE', 'failing_control': |
| `TST-SEC-006` | PASS | 4/4 refused with zero tier calls and the uniform response |
| `TST-SEC-007` | PASS | wrong-label chunk retrieved: True; outcome WITHHELD_VERIFICATION_MISMATCH; mismatches [{'chunk_id': '4a252927-0f8a-43d2-bd29-018487bc1971', 'reason': 'LABEL_MISMATCH'}]; generation invoked False; after re-ingest D-03 §4 retrieved for P-01: False |

## Failure experiments

| Test | Status | Key observation |
|---|---|---|
| `TST-SEN-001` | PASS | baseline PASS → variant FAIL (DETECTED AND CONTAINED every leaked request before generation) → variant destroyed, cleanup verified → restored PASS |

| Test | Status | Key observation |
|---|---|---|
| `TST-SEN-002` | PASS | baseline PASS → variant FAIL (DETECTED the authoritative classification mismatch and withheld) → variant destroyed, cleanup verified → restored PASS |

| Test | Status | Key observation |
|---|---|---|
| `TST-SEN-003` | PASS | baseline PASS → variant FAIL (did not contain it: verification checks chunks against the request's decision, and the decision itself was built from stale claims) → variant destroyed, cleanup verified → restored PASS |

## `fresh-20260915-r3-TST-OPS-001`

| Test | Status | Key observation |
|---|---|---|
| `TST-OPS-001` | PASS | every step exited 0; results match the reference run; cleanup verified |

## `fresh-20260915-r3-normal-all`

| Test | Status | Key observation |
|---|---|---|
| `TST-CHG-001` | PASS | same token: True (groups claim ['domain.BID-ORION']); before retrieved D-03 §4: True; after revocation retrieved BID-ORION: []; decision domains [] grants_version 2 (revoked version 2) |
| `TST-CHG-002` | PASS | before: D-13 retrieved True; after reclassification: [('P-01', 'WITHHELD_VERIFICATION_MISMATCH'), ('P-07', 'WITHHELD_VERIFICATION_MISMATCH')]; after restore + re-index: ANSWERED |
| `TST-DATA-001` | PASS | quarantine ['LABEL_MISSING']; absent from both tiers: True; P-01 retrieved ['D-01-S1', 'D-02-S1', 'D-02-S2', 'D-04-S1', 'D-13-S1'] |
| `TST-DATA-002` | PASS | {'D-10': {'reasons': ['LABEL_INVALID'], 'absent': True, 'ok': True}, 'D-11': {'reasons': ['SCOPE_MISSING'], 'absent': True, 'ok': True}, 'D-15': {'reasons': ['LABEL_INVALID'], 'absent': True, 'ok': True}}; quarantined sections retrieved: [] |
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
| `TST-OBS-001` | PASS | 90 audit items, 456 log events scanned; canary hits []; question hits 0; log hits {}; model logging enabled False |
| `TST-OBS-002` | PASS | reconstruction checks [{'decision': True, 'constraint_hashes': True, 'verification': True, 'outcome': True}, {'decision': True, 'constraint_hashes': True, 'verification': True, 'outcome': True}, {'decision': True, 'constraint_hashes': True, 'verification': Tru |
| `TST-SCALE-001` | PASS | P-10 retrieved D-08: True, leaks [], constraint [926] bytes, decision 4 ms; P-11 outcome REFUSED_CONSTRAINT_INCOMPLETE, tiers []; largest application-accepted constraint (445 grants, 8177 bytes) accepted by the service: True, last grant honoured: True; above t |
| `TST-SEC-001` | PASS | statuses {'missing': 401, 'malformed': 401, 'tampered_signature': 401, 'other_application': 401, 'expired': 401}; audit items before 93 after 93 |
| `TST-SEC-002` | PASS | token groups ['case.HR-2031', 'domain.BID-ORION']; decision domains [] cases [] = store []/[] v1: True; tiers ['shared']; leaks [] |
| `TST-SEC-003` | PASS | constraint hashes identical to baseline: True; D-12 (injected text) retrieved: True; leaks [] |
| `TST-SEC-004` | PASS | every capability held only by its intended principal; direct invocation denied (AccessDeniedException) |
| `TST-SEC-005` | PASS | during fault {'P-01': {'outcome': 'REFUSED_AUTHORIZATION_UNAVAILABLE', 'failing_control': 'CTL-004', 'tiers_called': [], 'retrieval': [], 'generation_invoked': False, 'uniform': True}, 'P-02': {'outcome': 'REFUSED_AUTHORIZATION_UNAVAILABLE', 'failing_control': |
| `TST-SEC-006` | PASS | 4/4 refused with zero tier calls and the uniform response |
| `TST-SEC-007` | PASS | wrong-label chunk retrieved: True; outcome WITHHELD_VERIFICATION_MISMATCH; mismatches [{'chunk_id': '1b7e0f8f-7f5e-4063-a6b4-62b99d1e4c86', 'reason': 'LABEL_MISMATCH'}]; generation invoked False; after re-ingest D-03 §4 retrieved for P-01: False |

## `primary-20260915-cleanup-all`

| Test | Status | Key observation |
|---|---|---|
| `CLEANUP` | PASS | CLEAN — normal, eligibility-removed, labels-corrupted, claims-as-grants |

## `fresh-20260915-r3-cleanup-all`

| Test | Status | Key observation |
|---|---|---|
| `CLEANUP` | PASS | CLEAN — normal, eligibility-removed, labels-corrupted, claims-as-grants |

## `sen1-primary-20260915-verdict`

| Test | Status | Key observation |
|---|---|---|
| `TST-SEN-001` | FAIL | baseline not all PASS |

## Notes

- **Experiment 1, first attempt** (`sen1-primary-20260915-*`): verdict FAIL only because one baseline request timed out on the client side (TST-ELG-003 ERROR); its variant failed as predicted, cleanup was verified and the restored run passed. The harness then retried client network timeouts once (recorded) and the experiment was repeated (`sen1-primary-20260915-r2-*`, PASS). Both attempts are kept.
- **Fresh copy:** attempts 1 and 2 were stopped by the operating system for low memory on the operator's machine (`fresh-20260915-attempt1-interrupted/`, `fresh-20260915-r2-interrupted/`) — not test results; their deployments were destroyed and cleanup verified. Attempt 3 (`fresh-20260915-r3-*`) ran unattended from a clean clone and matched the primary run.
- **Experiment 1** shows the security boundary failing at retrieval; verification detected and contained every leaked request before generation. That is detection and containment, not the architecture remaining safe.
- **Experiment 3** shows a leak verification cannot contain: it checks chunks against the request's decision, and the decision came from stale token claims.
- `LATENCY_SUMMARY.md` — per-stage latency from the primary run's audit records. `relevance-calibration/` — see `06-validation/RELEVANCE_CALIBRATION.md`. `filter-limit-measurement/` — see `05-implementation/PLATFORM_VERIFICATION.md` §6.
- Observed behaviour under the tested conditions only: platform limits, propagation times, scores and latency can change.
- **Field rename after the runs:** in every `inventory.json` the vector identifier field `key` was renamed `vector_id` (values unchanged) so generic secret scanners do not flag random chunk identifiers as API keys.
