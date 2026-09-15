# Run sen1-primary-20260915-variant

- Deployment: `tla-s01e02-sen-eligibility` (variant `eligibility-removed`)
- Started 2026-09-15T07:02:08+00:00 · finished 2026-09-15T07:03:10+00:00
- PASS 0 · FAIL 4 · ERROR 0

| Test | Status | Observed |
|---|---|---|
| `TST-ELG-003` | FAIL | precondition: P-02 retrieved D-03 §4 immediately before; LEAKS [{'persona': 'P-01', 'question': 'orion_pricing', 'leaked': ['CANARY-BID-ORION-PRICING-7Q3', 'CANARY-CLAIMS-INTERNAL', 'CANARY-HR2031-CASE-P8', 'CANARY-SI041 |
| `TST-ELG-005` | FAIL | precondition: P-04 retrieved D-07; LEAKS [{'persona': 'P-03', 'question': 'sec_vuln', 'leaked': ['CANARY-HR2031-CASE-P8', 'CANARY-SEC-SIG-VULN-3F', 'CANARY-SI0417-WITNESS-K2']}, {'persona': 'P-03', 'question': 'What are  |
| `TST-ELG-006` | FAIL | preconditions: P-05 and P-06 retrieved their cases; leaks [{'persona': 'P-07', 'question': 'si0417_witness', 'leaked': ['CANARY-HR2031-CASE-P8', 'CANARY-SI0417-WITNESS-K2']}, {'persona': 'P-07', 'question': 'hr2031', 'le |
| `TST-ELG-009` | FAIL | P-05 restricted tier searched: True; P-02 shared tier searched: True; leaks [{'persona': 'P-05', 'question': 'hr2031', 'leaked': ['CANARY-HR2031-CASE-P8']}, {'persona': 'P-02', 'question': 'finance', 'leaked': ['CANARY-F |
