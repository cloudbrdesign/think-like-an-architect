<!-- template: tla-requirements/1 -->
# Requirements — Kestrelmoor Knowledge Assistant: keeping the knowledge base current

**Status:** accepted (2026-09-16) — the Episode 03 baseline requirement set.
Future additions must trace to the business problem, a stakeholder, a constraint, a discovered risk, a validation finding
or a recorded decision; requirements are not added to make the architecture more sophisticated.

**Rules for this set**
- **What, not how:** requirements state what must be true, never which service or mechanism provides it. IDs are stable
  once approved.
- **Source column:** names the objective (OBJ-n in the brief), stakeholder, constraint or inherited Episode 02 residual
  risk.
- **Validation theme:** names a proposed theme in [VALIDATION_PLAN.md](../06-validation/VALIDATION_PLAN.md). Test IDs
  (TST-…) are assigned at the validation design gate, not here.
- **Related questions:** names decision questions in
  [ARCHITECTURE_DECISION_QUESTIONS.md](../04-decisions/ARCHITECTURE_DECISION_QUESTIONS.md).
- **INVARIANT:** marks a property that must hold at all times. "Never" states the invariant; it is not a claim that the
  property is guaranteed. Each invariant needs a test shown able to fail.
- **Windows:** the durations below are **approved working values for this fictional engagement**. They are
  design inputs for Kestrelmoor, never universal or industry requirements.

**Vocabulary**
- **authoritative record** — the records system's entry for a document or section: content version, status (in force,
  superseded, withdrawn, deleted), effective-from time, classification and scope, retention;
- **change** — any authoritative event that alters a record: create, new version, supersede, withdraw, reclassify
  (upward or downward), delete;
- **change class** — a group of changes with one freshness window and one behaviour while pending;
- **derived copy** — anything built from content: index entries, embeddings, cached answers, evaluation sets, exports,
  backups of those;
- **freshness lag** — the time between a change becoming effective in the authoritative record and the assistant
  reflecting it;
- **pending window** — the period during which a change is effective in the record but not yet reflected in the index.

## Business

| ID | Requirement | Rationale | Priority | Source | Validation theme | Related questions |
|---|---|---|---|---|---|---|
| BUS-001 | A procedure or bulletin that has been superseded or withdrawn is never presented as current guidance after its effective time | Superseded maintenance procedures are a safety hazard | MUST | OBJ-1 · Head of Engineering Safety | VT-1 | DQ-A, DQ-C |
| BUS-002 | Document owners revise, supersede, withdraw, reclassify and delete content only through the records system; the assistant requires no additional owner steps | Owners already maintain the authority; a second process would drift | MUST | Records Manager · CON-006 | review | DQ-A |
| BUS-003 | Company-wide rollout, including night shifts, proceeds without planned interruptions to answering for re-indexing | Depot work runs around the clock | SHOULD | OBJ-2 · COO · CON-004 | VT-9 | DQ-H |

## Functional

| ID | Requirement | Rationale | Priority | Source | Validation theme | Related questions |
|---|---|---|---|---|---|---|
| FUN-001 | Every answer cites the document, section, version and effective date of the content it used | Users and supervisors must be able to see what an answer is based on | MUST | OBJ-1 · Depot Maintenance Managers | VT-2 | DQ-D |
| FUN-002 | When the current content for a question is not yet available, the response says so plainly and never substitutes content known to be superseded, withdrawn or out of date — without revealing restricted material | Honest unavailability is safe; a stale answer is not | MUST | OBJ-3 · Depot technicians · CISO | VT-1, VT-2 | DQ-C |
| FUN-003 | A newly published version becomes answerable within the window for its change class (FRS-001) | Containment must end | MUST | OBJ-2 · OBJ-3 | VT-2, VT-8 | DQ-B, DQ-F |

## Freshness and consistency

| ID | Requirement | Rationale | Priority | Source | Validation theme | Related questions |
|---|---|---|---|---|---|---|
| FRS-001 | Each change class has an agreed freshness window and an agreed behaviour while pending. Approved working values: supersede or withdraw — effective in answers from the next request; upward reclassification — next request (inherited); new version — answerable within 4 hours; downward reclassification — within 24 hours; deletion from all derived copies — within the obligation window (ASM-006, ASM-007). **Safety semantics are locked; mechanisms are not.** The pending behaviour for a new version is deliberately left open for the options gate | "Current enough" differs by consequence | MUST | OBJ-2 · OBJ-3 | VT-8 | DQ-C, DQ-F |
| FRS-002 | **INVARIANT.** Content whose authoritative record is superseded, withdrawn or deleted is never used in an answer as current once that status is effective — whether or not the index has been updated. **This is an externally observable safety property, not a statement that derived state updates instantly** (2026-09-16); how it holds while derived state converges is an architecture question, and prevention takes effect from the next request after the authoritative change is effective | Incident 1: verification passed for a document that was valid but no longer in force | MUST | OBJ-1 · Head of Engineering Safety · E02 RR-04 | VT-1, VT-6 | DQ-A, DQ-C |
| FRS-003 | No answer combines sections from two versions of the same document; once a new version is answerable, the previous version's content is not retrievable | Old and new chunks coexist during replacement | MUST | OBJ-1 | VT-2 | DQ-D |
| FRS-004 | **INVARIANT.** Every authoritative change is either reflected in the index or recorded as failed, retried and escalated; no change is silently lost. The architecture must show **both** change delivery **and** change-loss detection; no delivery mechanism is assumed reliable because of the service that later implements it | Incident 2: a partial run failed and nothing alerted | MUST | OBJ-5 · Platform team | VT-4, VT-5 | DQ-B, DQ-G |
| FRS-005 | **INVARIANT.** Changes to the same document take effect in authoritative order; a late, duplicate or replayed change never reinstates an older version, an older label or a deleted document | Retries and replays are normal operating conditions | MUST | OBJ-1 · CISO | VT-3 | DQ-B, DQ-G |
| FRS-006 | Applying the same change more than once produces the same index state as applying it once | Retries must be safe | MUST | Platform team | VT-3 | DQ-G |
| FRS-007 | The index is regularly reconciled against the authoritative records, and missing, extra and stale content is detected and repaired without manual rebuilding | Detects what event handling misses | MUST | OBJ-5 · RSK-02 | VT-4 | DQ-B, DQ-H |
| FRS-008 | Freshness is measured per change class: lag from authoritative change to index, the age of the oldest pending change, and the count of failed changes | Freshness that cannot be measured cannot be promised | MUST | OBJ-5 · Internal Audit | VT-8 | DQ-F |

## Security

| ID | Requirement | Rationale | Priority | Source | Validation theme | Related questions |
|---|---|---|---|---|---|---|
| SEC-001 | **INVARIANT (inherited from Episode 02).** No change processing, retry, rebuild, rollback or reconciliation makes content retrievable by a requester who is not eligible for it — not even transiently | A change pipeline is also a disclosure path | MUST | OBJ-6 · CISO · CON-002 | VT-5, VT-7, VT-10 | DQ-D, DQ-G, DQ-H |
| SEC-002 | A downward reclassification never takes effect in answers before it is effective in the authoritative record; an upward reclassification continues to take effect from the next request | Lowering a label early is a disclosure; raising it late is the Episode 02 risk | MUST | OBJ-6 · Head of Safety Investigations | VT-7 | DQ-C |
| SEC-003 | Only the ingestion path can write to or remove from the index, and it acts only on changes that come from the authoritative records system | Unauthorised writes or deletions corrupt both freshness and eligibility | MUST | CISO | VT-5 | DQ-B |
| SEC-004 | Text inside a document never changes another document's status, version, classification or retention (for example "this procedure supersedes MP-114") | Content is untrusted input; status comes from records | MUST | CISO · RSK-11 | VT-1 | DQ-A |
| SEC-005 | Freshness, failure and deletion records contain identifiers, versions, times and outcomes — never document content | The Episode 02 content-free audit principle extends to change processing | MUST | DPO · CISO | VT-6, VT-8 | DQ-F |

## Data

| ID | Requirement | Rationale | Priority | Source | Validation theme | Related questions |
|---|---|---|---|---|---|---|
| DATA-001 | A deletion reaches every **active** derived copy within its obligation window. The derived-copy surface is derived from the selected architecture, not assumed from a list. Backups are governed by retention expiry, not routine restore-and-redelete | Incident 3: deleted in the records system, not deleted everywhere | MUST | OBJ-4 · Procurement · DPO | VT-6 | DQ-E |
| DATA-002 | The index can be rebuilt entirely from the authoritative records; nothing in it is authoritative | A derived copy that cannot be rebuilt becomes a second authority | MUST | Records Manager · CON-001 | VT-9 | DQ-H |
| DATA-003 | Superseded and withdrawn content retained in the records system for history is not retrievable by the assistant unless an explicit historical capability is approved | History is a records-system function, not an answering function | MUST | Head of Engineering Safety | VT-1 | DQ-A, DQ-D |
| DATA-004 | Every deletion produces content-free evidence of which derived copies were removed and when | Obligations must be demonstrable | MUST | OBJ-4 · Internal Audit | VT-6 | DQ-E |

## Non-functional

| ID | Requirement | Rationale | Priority | Source | Validation theme | Related questions |
|---|---|---|---|---|---|---|
| NFR-001 | Freshness windows hold at the assumed daily change volume and at a burst the size of a safety bulletin or reclassification campaign (ASM-002, ASM-004) | Bursts are when freshness matters most | SHOULD | OBJ-2 · RSK-08 | VT-9 | DQ-G |
| NFR-002 | A full rebuild or large reprocessing does not stop answering from the current index and does not widen eligibility | Night shifts; CON-004 | SHOULD | COO · CISO | VT-9, VT-10 | DQ-H |
| NFR-003 | The pending (withheld or unavailable) window for each change class is bounded, measured and reported; exceeding it is treated as an incident | Containment must not become indefinite over-blocking | SHOULD | OBJ-3 · RSK-07 | VT-8 | DQ-C, DQ-F |

## Operational

| ID | Requirement | Rationale | Priority | Source | Validation theme | Related questions |
|---|---|---|---|---|---|---|
| OPS-001 | Failed or stuck changes and freshness-window breaches raise an alert naming the change class and affected identifiers | Incident 2 went unnoticed for three days | MUST | OBJ-5 · Platform team | VT-4, VT-5 | DQ-F, DQ-G |
| OPS-002 | Operators can reprocess one document, a batch of changes or the whole corpus, with a recorded reason, without an engineering change | Repair must be routine and safe | MUST | Platform team | VT-4, VT-9 | DQ-H |
| OPS-003 | Freshness and deletion reports are available to safety assurance and internal audit on request | Evidence of when a bulletin became effective | SHOULD | Internal Audit · Safety Assurance | VT-8 | DQ-F |

## Compliance — Kestrelmoor policy and contract positions

| ID | Requirement | Rationale | Priority | Source | Validation theme | Related questions |
|---|---|---|---|---|---|---|
| CMP-001 | A supplier's proprietary documents are removed from every derived copy within the contractual window after the contract ends (ASM-006) | Contractual obligation owned by Procurement | MUST | Procurement and Commercial Director | VT-6 | DQ-E |
| CMP-002 | An erasure approved by the Data Protection Officer reaches every derived copy of the affected personal data within Kestrelmoor's policy window (ASM-007) | Policy position set by the DPO; not legal advice | MUST | DPO | VT-6 | DQ-E |

---

**Count:** 31 requirements (26 MUST, 5 SHOULD) · 4 invariants (FRS-002, FRS-004, FRS-005, SEC-001). **Baseline** (2026-09-16).
