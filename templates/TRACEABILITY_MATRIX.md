<!-- template: tla-traceability-matrix/1 -->
# Traceability Matrix — <engagement title>

```
business problem → requirement → decision → control → test → observed result → portfolio evidence
```

One row per requirement-to-test link. This matrix answers two questions for anyone reviewing your work:
**"Which requirement drove this decision?"** and **"Which test demonstrates that this requirement is satisfied?"**

Rules (checked by `tools/traceability_check.py`):
- keep the header exactly as below; separate multiple IDs with commas;
- every ID you reference must be defined in your requirements, ADRs or validation plan;
- every `MUST` requirement appears here with a test, or with `review: <rationale>` in the Test column;
- observed result is one of `NOT RUN`, `PASS`, `FAIL`, `NOT VERIFIED`, `NOT APPLICABLE`;
- a `PASS` or `FAIL` result points to evidence by relative path inside your episode folder.

| Requirement | Decision | Control | Test | Observed result | Evidence |
|---|---|---|---|---|---|
| SEC-000 | ADR-000 | CTL-000 | TST-AREA-000 | NOT RUN | — |
