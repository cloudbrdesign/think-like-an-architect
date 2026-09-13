# Architecture Decision Questions — Veltamere Document Assistant

These are the questions the architecture stage must answer. **None is answered here.** Where options are listed, they are
candidates to evaluate — not a shortlist with a hidden winner. Each question becomes an options analysis and, where the
decision is consequential, an architecture decision record.

**Try to answer each question yourself before reading any later material.**

---

## DQ-A — Tenant isolation model

**Decision question:** What is the unit of isolation, and is isolation enforced **logically** inside shared structures,
**physically** through separate structures or environments per tenant, or through a mix?

**Questions to resolve**
- What does "tenant boundary" mean for documents, for derived retrieval data and for records?
- Does the answer change for very large tenants, or tenants with stricter contracts?
- What does each option cost to operate for a five-person team as tenants grow towards 400 (ASM-001, CON-003)?
- What fails first, and how visibly, under each option?

**Options to evaluate:** shared retrieval structures with tenant ownership enforced on every query · a separate retrieval
structure per tenant within one shared platform · a separate environment per tenant · a hybrid by tenant size or contract.

**Driven by:** SEC-001, SEC-004, NFR-002, NFR-004, CMP-001, CMP-002 · CON-002, CON-003, CON-008 · RSK-01, RSK-09, RSK-13

---

## DQ-B — Tenant identity source

**Decision question:** Which component is trusted to establish a user's tenant context, and how does that context reach the
components that authorise and retrieve without the caller being able to change it?

**Questions to resolve**
- Where does user identity originate (CON-004), and where is it verified?
- How is tenant membership established, and how are users who belong to several tenants handled (ASM-004)?
- Can a caller supply or alter a tenant identifier anywhere on the path? What is ignored, and what is rejected?
- What happens when identity or tenant membership is missing, expired or inconsistent?
- How will the learner implementation represent the existing identity provider without changing what is being taught?

**Options to evaluate:** tenant context taken from verified identity claims · tenant context resolved server-side from
the verified user identity · verified claims confirmed against a membership lookup.

**Driven by:** SEC-002, SEC-003, SEC-008 · CON-004 · ASM-004, ASM-005 · RSK-02, RSK-03

---

## DQ-C — Authorisation enforcement point

**Decision question:** Where exactly is the decision "this user may retrieve from this tenant's documents" made, and what
guarantees that no path reaches documents or retrieval data without it?

**Questions to resolve**
- Is there one enforcement point, or several layers — and which layer is the one that must never be missing?
- Which component fails closed, and what does "closed" return?
- How do support and administrative functions differ from tenant users, and how are they kept from becoming a bypass?
- Which credentials does each component hold, and what could each do if misused (SEC-010)?

**Options to evaluate:** authorisation in the application service before retrieval is called · a dedicated authorisation
component in front of retrieval · access control enforced by the retrieval store itself with tenant-scoped access · a
layered combination.

**Driven by:** SEC-002, SEC-004, SEC-008, SEC-009, SEC-010 · RSK-02, RSK-03, RSK-07, RSK-08

---

## DQ-D — Document and ingestion tenant attribution

**Decision question:** How does each document — and everything derived from it — receive its owning tenant, which
component is trusted to set it, can it ever change, and what happens when it is wrong?

**Questions to resolve**
- Who owns each document, and where does ownership enter the system?
- Is attribution derived from the authenticated uploader, from where the document is stored, or from something else?
- Is attribution immutable? If not, who may change it, and how is that recorded (SEC-007)?
- How is a mis-attributed document detected, contained or corrected (DATA-003, RSK-04)?
- How do deletion (FUN-003, ASM-008) and disabling a tenant (BUS-001) reach derived data?

**Options to evaluate:** attribution assigned by the ingestion process from the uploader's verified tenant · attribution
derived from a platform-controlled storage location · attribution validated against the tenant record with quarantine
for anomalies · immutable attribution with a recorded administrative correction path.

**Driven by:** SEC-006, SEC-007, DATA-001, DATA-002, DATA-003, FUN-002, FUN-003, BUS-001 · ASM-005, ASM-006, ASM-008 ·
RSK-04, RSK-12

---

## DQ-E — Retrieval boundary

**Decision question:** What guarantees that retrieval only ever considers the authorised tenant's content — **before** any
content reaches a model — and how could that guarantee be bypassed?

**Questions to resolve**
- Is the tenant constraint part of the retrieval itself, a choice of which structure to search, or enforced by the store?
- What happens if the constraint is empty or missing (SEC-008)?
- Can instructions in a question or in a document change what is retrieved (SEC-005)?
- Which output channels could carry another tenant's information: results, answers, citations, metadata, caches?
- How is the boundary exercised so that a test could actually fail (RSK-14)?

**Options to evaluate:** a tenant constraint applied inside every retrieval · retrieval scoped by selecting a tenant-specific
structure · document-level access control enforced by the retrieval store · checks after retrieval as defence in depth
only (SEC-004 rules them out as the control).

**Driven by:** SEC-001, SEC-004, SEC-005, SEC-008, DATA-002, FUN-001 · RSK-01, RSK-03, RSK-05, RSK-06, RSK-11, RSK-15

---

## DQ-F — Audit and observability boundary

**Decision question:** What must be recorded about each authorisation decision and retrieval to investigate a suspected
exposure, where is it recorded, who may read it, and how is document content kept out of those records?

**Questions to resolve**
- Which fields let an investigator connect a user, a tenant context, a decision and the documents retrieved (OPS-001)?
- How are refused and failed-closed requests distinguished from successful ones?
- Do the records themselves need tenant isolation?
- How long are records kept, and does that fit the contractual notification and evidence duties (CMP-001)?

**Options to evaluate:** decision records written by the component that authorises · access records from the retrieval
layer · one correlated record per question across components · retention and access-control choices for each.

**Driven by:** OPS-001, OPS-002, CMP-001, SEC-011 · RSK-08, RSK-10, RSK-11

---

## Cross-cutting questions

- **Shared content:** if any content must ever be shared across tenants, how is it kept distinct from tenant content (ASM-007)?
- **Lifecycle:** what is the minimum deletion and disablement behaviour this episode must prove, and what is left to
  Episode 03 (FUN-003, BUS-001)?
- **Trust:** list every component that is trusted. Which one, if wrong, breaks isolation on its own?
- **Evidence:** which tests, observed failing when the control is removed, will prove the boundary works (TST-SEN-011)?
