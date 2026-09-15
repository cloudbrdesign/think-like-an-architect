# Architecture Decision Questions — Kestrelmoor Knowledge Assistant

**Status:** accepted (2026-09-15).

These are the questions the architecture must answer. **Try to answer each one yourself** before reading the options
analysis. The listed options are candidates to evaluate, not a shortlist with a hidden winner.

> **Proposed answers, after you have tried:**
> - DQ-A → ADR-001
> - DQ-B and DQ-C → ADR-003
> - DQ-D → ADR-004
> - DQ-E → ADR-002
> - DQ-F → ADR-005
> - DQ-G → ADR-006
>
> The comparison is in [ARCHITECTURE_OPTIONS_ANALYSIS.md](ARCHITECTURE_OPTIONS_ANALYSIS.md).

---

## DQ-A — What is the authorization and sensitivity model?

**Decision question:** How are "how sensitive" and "who may see it" represented, so that eligibility can be computed
mechanically and need-to-know is honoured?

**Questions to resolve**
- Is sensitivity a ladder (higher clearance sees more) or a set of compartments (specific grants see specific things)?
- What does an operations director see of an HR case they are not assigned to?
- Which attributes of a person are authorization inputs, and which are deliberately not?

**Options to evaluate:** hierarchical clearance levels · role- and department-based groups · labels with scopes plus
explicit entitlements · per-document access lists copied from the records system.

**Driven by:** SEC-001, SEC-006, FUN-002, BUS-001, BUS-002, BUS-003 · RSK-05

## DQ-B — Where does classification come from, and at what granularity?

**Decision question:** Who is authoritative for a section's sensitivity, how does that label reach every chunk, and what
happens when it is missing or wrong?

**Questions to resolve**
- Document-level labels, section-level labels, or automated classification?
- Can a chunk ever be less restricted than its document? Can a chunk span two sections?
- What happens to unlabelled or malformed documents, and to text inside a document that claims its own classification?

**Options to evaluate:** document-level owner labels only · section-level owner labels from the records system ·
automated classification at ingestion as the authority · owner labels as the authority plus automated detection as
advice.

**Driven by:** DATA-001, DATA-002, DATA-003, DATA-005, DATA-007, FUN-004, SEC-007 · CON-002, CON-007 · RSK-01, RSK-02

## DQ-C — What should never be indexed?

**Decision question:** Is there content that no assistant use case needs, and should it be excluded before it can become
a retrieval problem?

**Questions to resolve**
- Does any approved use case need medical details from investigation reports?
- If content is eligible for nobody through the assistant, why hold it in the index at all?

**Options to evaluate:** index everything someone could be eligible for · exclude special-category content · index only
sanitised summaries of RESTRICTED material.

**Driven by:** DATA-004, DATA-006, CMP-001 · OBJ-3

## DQ-D — Where is retrieval eligibility enforced, and how are the indexes organised?

**Decision question:** What technical boundary guarantees that ineligible sections are never retrieval candidates, and
should content of different sensitivity share a structure?

**Questions to resolve**
- Does a defect in one constraint expose everything, or only one tier?
- How many separate structures would per-domain or per-case separation mean, given ASM-002?
- What happens to cross-domain questions under each option?
- What does filtering after retrieval expose, even when it "works"?

**Options to evaluate:**
- separate indexes per access domain or case;
- one shared index with a mandatory eligibility constraint;
- sensitivity-tiered indexes, each with a mandatory constraint;
- retrieve broadly, then decide eligibility per chunk;
- prompt instructions;
- redaction of generated answers.

**Driven by:** SEC-001, SEC-004, SEC-005, SEC-009, SEC-013, NFR-002, NFR-004 · CON-004 · RSK-09

## DQ-E — Where do entitlements come from, and when is the decision made?

**Decision question:** Which component decides eligibility, from which authoritative inputs, and at what moment?

**Questions to resolve**
- Can token group claims be trusted for domain memberships and case assignments (ASM-008)?
- What happens to a revoked grant during an active session?
- What does the system do if the entitlement source is unavailable?

**Options to evaluate:** token claims · per-request resolution from the entitlement sources by a policy decision point ·
a periodically refreshed entitlement snapshot.

**Driven by:** SEC-002, SEC-003, SEC-007, SEC-010, NFR-001, NFR-002, NFR-003 · CON-003 · RSK-03

## DQ-F — What happens between retrieval and generation, and in the response?

**Decision question:** How is a stale, tampered or mis-evaluated label caught before content reaches the model, and how do
answers, citations and refusals avoid disclosing restricted material?

**Questions to resolve**
- What should the system compare a retrieved chunk against, and what does a mismatch mean?
- Withhold the whole answer, or silently drop the mismatched chunk?
- What does "cannot answer" look like, so that it reveals nothing?
- Which answers may be cached?

**Options to evaluate:** trust retrieval · re-verify each chunk against the current classification record and withhold on
mismatch · re-verify and drop mismatched chunks.

**Driven by:** SEC-008, SEC-011, FUN-003, DATA-006 · RSK-04, RSK-08

## DQ-G — What is recorded, and what must never be?

**Decision question:** How can every decision be explained later without the audit trail becoming a copy of sensitive
content or disproportionate monitoring of staff?

**Questions to resolve**
- What does an investigator need in order to answer "why could this person see that section?"
- Is the question text itself sensitive?
- How long are records kept?

**Options to evaluate:** full request/response logging · content-free decision records with source versions · no
per-request records.

**Driven by:** SEC-012, OPS-001, OPS-002, CMP-002 · RSK-06
