<!-- template: tla-adr/1 -->
# ADR-006 — Content-free audit records and decision reconstruction

**Status:** accepted (2026-09-15) · **Date:** 2026-09-15 · **Answers:** DQ-G · **Options:** [section 7](ARCHITECTURE_OPTIONS_ANALYSIS.md#7-audit--adr-006)

## Context

Kestrelmoor must be able to answer: *why could this person see that section, or why was their answer withheld?*

**The constraint.** The audit trail must not become a second copy of witness statements or bid pricing. Nor may it be a
disproportionate record of what staff ask.

**Requirements:** SEC-012, OPS-001, OPS-002, CMP-002, DATA-006.

## Decision

**What each request records:**
- the employee identifier;
- the versions of the entitlement and classification records used;
- the eligibility decision (label set, scope IDs);
- a hash of each tier constraint;
- for every retrieved or withheld chunk: its identifier, label, scope and reason;
- the outcome and timings;
- the question as a keyed hash only.

**What is never recorded:** document content, excerpts, answer text or question text.

**Logging:**
- operational logging and tracing never capture request or response bodies, prompts or completions;
- model invocation content logging is off.

**Reports:** quarantine and verification-mismatch reports go to the records manager and security team.

**Reconstruction:** a past decision is reconstructed from the record and the stored source versions.

**Retention:** per Kestrelmoor records policy (CMP-002).

## Alternatives considered

- **Full request/response logging:** fails SEC-012.
- **No per-request records:** fails OPS-002.

## Rationale

**Explainability comes from decisions and versions, not from copies of content.**

## Consequences

- **Positive:**
  - investigations are possible without creating a sensitive log estate;
  - staff monitoring stays proportionate.
- **Negative / accepted trade-offs:**
  - debugging answer quality cannot rely on logged prompts;
  - quality evaluation needs synthetic or consented datasets.

## Risks

**Content logging enabled later during an incident** (RR-09).

## Controls introduced

| ID | Control | Enforcement point |
|---|---|---|
| CTL-018 | Content-free audit record per request: identifiers, source versions, decision, labels and scope IDs, constraint hashes, outcomes; question as keyed hash only | Audit |
| CTL-019 | Operational logs, traces and model invocation logging never capture bodies, prompts, completions or excerpts | All components; logging configuration |
| CTL-020 | Decision reconstruction from audit records and stored entitlement/classification versions; quarantine and mismatch reports delivered to owners | Audit and reporting |

## Related
- **Requirements:** SEC-012, OPS-001, OPS-002, CMP-002, DATA-006.
- **Tests:** TST-OBS-001, TST-OBS-002.
- **Validation implication:** every canary is searched for in every audit record and log produced during the whole
  validation run.
