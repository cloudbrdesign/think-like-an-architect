<!-- template: tla-adr/1 -->
# ADR-003 — Classification authority, section granularity and minimisation at ingestion

**Status:** accepted (2026-09-15) · **Date:** 2026-09-15 · **Answers:** DQ-B, DQ-C · **Options:** [sections 2–3](ARCHITECTURE_OPTIONS_ANALYSIS.md#2-classification-authority-and-granularity--adr-003)

## Context

**The problem.** Eligibility is only as correct as the labels it evaluates. Mixed documents put their most sensitive
section beside content everyone should read.

**The authority.** The records system is the classification authority (CON-002). Section marks exist for high-risk
document types (ASM-004). Some content — medical details — is needed by no use case.

**Requirements:** DATA-001 … DATA-007, FUN-004, SEC-007, CMP-001.

## Decision

1. **Authority:** ingestion reads labels and scopes only from the owner's classification record, for the document and
   each marked section. Classification text inside documents is ignored.
2. **Validation:**
   - a label outside the taxonomy is invalid;
   - so is CONFIDENTIAL without a domain, or RESTRICTED without a case;
   - so is a scope on an INTERNAL section.

   Invalid or missing labels exclude that document or section from the index and report it.
3. **Minimisation:** sections marked special-category are removed before any chunking, embedding or model call. They are
   never indexed.
4. **Granularity:**
   - chunks are produced within section boundaries;
   - the effective label and scope is the section's, or the document's when the section is unmarked, and never less
     restrictive than the document's;
   - each chunk records document, section, label, scope and record version.
5. **Routing:** INTERNAL and CONFIDENTIAL chunks go to the shared tier; RESTRICTED chunks go to the restricted tier only
   (ADR-004).

## Alternatives considered

- **Document-level only:** fails FUN-004; kept as the fallback for unmarked documents.
- **Automated classification as the authority:** fails CON-002 and DATA-002.
- **Advisory automated detection:** a possible extension; never an authorization source.
- **Indexing special-category content:** fails DATA-004.
- **Sanitised summaries only:** would remove the RESTRICTED use cases.

## Rationale

**One authority, the granularity mixed documents need, and fail-closed labels.** Minimisation removes the most harmful
content from the retrieval problem entirely.

## Consequences

- **Positive:**
  - mixed documents keep their INTERNAL value;
  - malformed metadata cannot become "everyone";
  - medical details cannot leak through the assistant, because they are not in it.
- **Negative / accepted trade-offs:**
  - unlabelled content is unavailable until labelled (RR-08);
  - labels are enforced, not validated for truth (RR-01);
  - re-indexing is needed when section marks change (RR-04).

## Risks

**Mislabelling at the source** (RR-01). **An unmarked special-category section** (ASM-006). **Routing defects**
(tested by TST-DATA-006).

## Controls introduced

| ID | Control | Enforcement point |
|---|---|---|
| CTL-006 | Labels and scopes read only from the records-system classification record; text-borne classification ignored | Ingestion |
| CTL-007 | Taxonomy and label/scope validation; invalid or missing classification excluded and reported | Ingestion |
| CTL-008 | Section-bounded chunking; effective label never less restrictive than the document; provenance and record version on every chunk | Ingestion |
| CTL-009 | Special-category sections removed before chunking, embedding or any model call | Ingestion |
| CTL-010 | Tier routing: RESTRICTED chunks only to the restricted tier; unknown labels to neither | Ingestion |

## Related
- **Requirements:** DATA-001, DATA-002, DATA-003, DATA-004, DATA-005, DATA-006, DATA-007, FUN-004, SEC-007, CMP-001.
- **Tests:** TST-ELG-004, TST-DATA-001 … TST-DATA-006, TST-SEN-002.
- **Validation implication:** TST-SEN-002 builds an ingestion variant that ignores section marks. The section test must
  fail there.
