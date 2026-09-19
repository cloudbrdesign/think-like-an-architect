# Architecture Decision Questions — Kestrelmoor Knowledge Assistant: keeping the knowledge base current

**Status:** accepted as the question set (2026-09-16). The answers are in the options analysis and the ADRs.

These are the questions the architecture must answer. **Try to answer each one yourself.** At this gate they are
questions only: the options analysis and architecture decision records follow at the next gate, after the definition is
approved. Candidate approaches are listed so the questions are concrete, not as a shortlist with a hidden winner.

---

## DQ-A — What is the unit and the authority of change?

**Decision question:** Which authoritative facts does the assistant need to know about a document or section to answer
safely and currently, and at what granularity does a change apply?

**Questions to resolve**
- Is a change about a document, a section, a version, or all three? What happens to section boundaries across versions?
- Which record attributes are inputs to answering: version, status, effective-from time, supersession, classification,
  retention?
- How is "superseded by another document" represented, and how is it distinguished from "new version of this document"?
- What must never be an input — for example, text in a document that claims to supersede another?

**Candidate approaches to evaluate:** status and version as query-time inputs · status resolved only at indexing ·
effective-date windows on content · supersession graph maintained from records.

**Driven by:** BUS-001, BUS-002, FRS-002, SEC-004, DATA-003 · RSK-01, RSK-11

## DQ-B — How do authoritative changes reach the index?

**Decision question:** How does the platform learn about every change, with what delivery guarantees, and how does it
know it has not missed one?

**Questions to resolve**
- Change notifications, periodic comparison with a full export, or both?
- What happens when notifications arrive twice, late, out of order, or not at all?
- How is ordering per document established — by the record's version, by time of arrival, or otherwise?
- Who is allowed to trigger a write or removal in the index?

**Candidate approaches to evaluate:** event-driven change processing · scheduled full or incremental comparison · event
processing with periodic reconciliation · owner-triggered reprocessing.

**Principle:** event delivery tells us about the changes we received; reconciliation must help us
discover the changes we did **not** receive. A notification stream never proves its own completeness.

**Driven by:** FUN-003, FRS-004, FRS-005, FRS-007, SEC-003 · RSK-02, RSK-03 · ASM-003

## DQ-C — What does the assistant do while a change is pending?

**Decision question:** Between a change becoming effective in the record and the index reflecting it, how does the
assistant answer — per change class — so that it is safe, honest and not indefinitely unavailable?

**Questions to resolve**
- Withhold, answer from the old content with a warning, answer only from content confirmed current, or something else —
  and does the answer differ for safety procedures, security classifications and ordinary documents?
- Which checks happen at query time against the authoritative record, and what do they cost when many records change?
- How is the pending window bounded, and what happens when it is exceeded?
- How does this extend the Episode 02 verification step without making it the only freshness control?

**Candidate approaches to evaluate:** withhold until current · answer with an explicit currency notice · query-time
status check against the record · class-specific behaviour.

**Locked by decision (safety semantics, not mechanism):** for supersede, withdraw and upward reclassification, the affected
content must not be answered under its old state from the next request after the authoritative change is effective;
deleted content must not continue to be presented as current. **Open:** the pending behaviour for a new version.

**The question is therefore not only** "how fast can derived state be rebuilt?" **but** "how does the request path know
that derived state must not currently be trusted?"

**Driven by:** BUS-001, FUN-002, FRS-001, FRS-002, SEC-002, NFR-003 · RSK-01, RSK-07

## DQ-D — How are versions replaced in the index?

**Decision question:** How does a new version replace an old one so that answers never mix versions and never see a gap
or a transient widening of eligibility?

**Questions to resolve**
- Update in place, write the new version alongside the old and switch, or remove then add?
- What does a reader see halfway through a replacement?
- How are citations kept tied to the version actually used?
- How are labels and content kept together so that content is never visible before its label?

**Candidate approaches to evaluate:** in-place replacement · versioned write with a switch · tombstone then re-index ·
per-document generation markers.

**Driven by:** FUN-001, FRS-003, SEC-001, DATA-003 · RSK-04, RSK-06

## DQ-E — How does deletion reach every derived copy, and how is it proven?

**Decision question:** Where do derived copies of content live, how does a deletion reach each of them within its window,
and what evidence shows it did?

**Questions to resolve**
- What is the complete inventory of derived copies (index entries, embeddings, caches, evaluation sets, exports, backups)?
- Is deletion immediate unretrievability plus later physical removal, or a single step?
- How are backups treated — excluded, expiry-based, or restore-and-redelete?
- What content-free evidence records completion?

**Candidate approaches to evaluate:** propagated deletion per store · deletion ledger with verification · expiry-based
backup position · periodic deletion reconciliation.

**Decided:** deletion is a derived-state problem, not an index operation. The derived-copy surface (chunks,
embeddings, indexes, intermediate artifacts, caches, queued payloads, operational stores, backups) is **derived from the
selected architecture**, not assumed from a list. Backups expire through retention; restore-and-redelete is not the normal
mechanism.

**Driven by:** DATA-001, DATA-004, CMP-001, CMP-002, SEC-005 · RSK-05 · ASM-006, ASM-007, ASM-009

## DQ-F — How is freshness measured, alerted and evidenced?

**Decision question:** What freshness is promised per change class, how is it measured, and how does the platform prove
when a change became effective in the assistant?

**Questions to resolve**
- Which measurements: lag per change class, oldest pending change, failed changes, reconciliation drift?
- Which windows are commitments, and which are targets?
- What evidence does safety assurance receive about a bulletin?
- How is a measurement shown to be non-vacuous (that it would detect an injected delay)?

**Candidate approaches to evaluate:** per-change timestamps end to end · freshness objectives with alerting · periodic
freshness reports · synthetic canary changes.

**Principle:** processing latency is not provable freshness. A fast pipeline does not show that the
index is current, that nothing was missed, or that convergence completed.

**Driven by:** FRS-001, FRS-008, NFR-003, OPS-001, OPS-003, SEC-005 · RSK-09

## DQ-G — How are failures, retries and bursts handled?

**Decision question:** How does change processing survive failures, poison documents and bursts without losing changes,
reordering them, or widening eligibility?

**Questions to resolve**
- What makes applying a change safe to repeat?
- How are changes that fail repeatedly isolated, reported and retried?
- How is a burst (a bulletin, a reclassification campaign, a migration) prioritised against steady-state changes — should
  safety-critical changes go first?
- What is the index state after a partial failure?

**Candidate approaches to evaluate:** idempotent change application · failed-change isolation with retry and escalation ·
priority by change class · checkpointed batch processing.

**Driven by:** FRS-004, FRS-005, FRS-006, NFR-001, OPS-001, SEC-001 · RSK-02, RSK-03, RSK-08

## DQ-H — How is the index repaired or rebuilt?

**Decision question:** How are drift and corruption repaired — targeted reprocessing, reconciliation or full rebuild —
without stopping answers or regressing eligibility?

**Questions to resolve**
- When is reconciliation enough, and when is a rebuild required?
- Can a rebuild run while the current index keeps answering, and how is the switch made safe?
- How is a rebuilt index shown to be equivalent to the authoritative records, including labels?

**Candidate approaches to evaluate:** continuous reconciliation · targeted reprocessing on demand · parallel rebuild with
a verified switch · periodic full rebuild.

**Driven by:** BUS-003, FRS-007, DATA-002, NFR-002, OPS-002, SEC-001 · RSK-06, RSK-10
