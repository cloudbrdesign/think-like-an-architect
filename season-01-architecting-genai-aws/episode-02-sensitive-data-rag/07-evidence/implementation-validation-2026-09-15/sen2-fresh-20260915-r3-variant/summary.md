# Run sen2-fresh-20260915-r3-variant

- Deployment: `tla-s01e02-sen-labels` (variant `labels-corrupted`)
- Started 2026-09-15T10:06:15+00:00 · finished 2026-09-15T10:06:33+00:00
- PASS 0 · FAIL 3 · ERROR 0

| Test | Status | Observed |
|---|---|---|
| `TST-DATA-005` | FAIL | 17 chunks checked; problems: [{'section': 'D-03-S4', 'tier': 'shared', 'problem': 'attributes differ from the record', 'indexed': ['INTERNAL', 'NONE'], 'record': ['CONFIDENTIAL', 'BID-ORION']}, {'section': 'D-04-S2', 'ti |
| `TST-DATA-006` | FAIL | problems: [{'section': 'D-04-S2', 'problem': 'authoritative tier restricted, found in shared'}, {'object': 'sections/D-04/S2.txt', 'problem': 'section object in the shared bucket'}]; cache resources []; cache settings [] |
| `TST-ELG-004` | FAIL | lessons retrieved+cited: False; D-03 §4 retrieved in: ['orion_lessons', 'orion_pricing']; leaks [{'persona': 'P-01', 'question': 'orion_lessons', 'leaked': ['CANARY-BID-ORION-PRICING-7Q3', 'CANARY-SI0417-WITNESS-K2']}, { |
