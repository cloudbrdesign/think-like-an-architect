<!-- template: tla-adr/1 -->
# ADR-005 — Pre-generation verification, withholding and response handling

**Status:** accepted (2026-09-15) · **Date:** 2026-09-15 · **Answers:** DQ-F · **Options:** [section 6](ARCHITECTURE_OPTIONS_ANALYSIS.md#6-between-retrieval-and-generation--adr-005)

## Context

**Three ways an indexed label can be wrong at query time:**
1. **Stale:** the section was reclassified upward after indexing (SEC-011).
2. **Tampered:** a chunk's metadata was changed after ingestion.
3. **Mis-evaluated:** the managed search evaluated the constraint incorrectly (RR-11).

**Two ways the response can disclose:**
- citations naming restricted sections;
- refusals revealing that restricted content exists.

**Requirements:** SEC-008, SEC-011, FUN-001, FUN-003, DATA-006.

## Decision

1. **Verify:** before generation, every retrieved chunk is re-checked:
   - its label, scope and section version against the **current** classification record;
   - its eligibility against the request's decision.
   Any mismatch withholds the **whole** answer, records a security event, and returns the uniform response.
2. **Citations:** only verified chunks, at section level, and only sections the requester is eligible for.
3. **Uniform response:** when no eligible content answers the question — or the answer is withheld — the response is
   identical to "nothing found" and names nothing.
4. **Caching:** answers built from CONFIDENTIAL or RESTRICTED content are never cached (caching policy for INTERNAL
   answers is Episode 05).

## Alternatives considered

- **Trust retrieval:** stale labels and defects go undetected.
- **Drop mismatched chunks silently:** hides defects and gives partial answers shaped by what was removed.

## Rationale

**Verification is detection, not prevention.** The prevention is ADR-004. Withholding turns a silent defect into a
visible, investigable event. Comparing against the current record makes upward reclassification effective before
re-indexing.

## Consequences

- **Positive:**
  - stale upward labels, tampering and mis-evaluated constraints are caught before content reaches the model;
  - refusals leak nothing.
- **Negative / accepted trade-offs:**
  - one classification-record read per retrieved chunk (latency; batched in design);
  - withheld answers while the index lags reclassification (RR-04);
  - by the time verification fires, content has already crossed the retrieval boundary — which is why it cannot replace
    ADR-004.

## Risks

**Classification record unavailable:** verification fails closed, so the whole answer is withheld.

## Controls introduced

| ID | Control | Enforcement point |
|---|---|---|
| CTL-014 | Every retrieved chunk re-checked against the current classification record and the decision; any mismatch withholds the whole answer and records a security event | Between search and generation |
| CTL-015 | Citations only from verified chunks, at section level, for eligible sections | Response builder |
| CTL-016 | Uniform "cannot answer from the content available to you" response for no eligible content and for withheld answers | Response builder |
| CTL-017 | No caching of answers that used CONFIDENTIAL or RESTRICTED content | Answer handling |

## Related
- **Requirements:** SEC-008, SEC-011, FUN-001, FUN-003, DATA-006.
- **Tests:** TST-SEC-007, TST-CHG-002, TST-ELG-008, TST-DATA-006, TST-SEN-001, TST-SEN-002.
- **Validation implication:** in both sensitivity variants, verification must fire (withheld), and the retrieval-layer
  observation must still show the leak — detection does not equal safety.
