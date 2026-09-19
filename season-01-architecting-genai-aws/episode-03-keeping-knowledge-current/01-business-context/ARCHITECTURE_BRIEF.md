<!-- template: tla-architecture-brief/1 -->
# Architecture Brief — Kestrelmoor Knowledge Assistant: keeping the knowledge base current

> Fictional scenario for learning. Kestrelmoor Rail Systems, its people, procedures, bulletins, suppliers and documents
> are invented. All engagement data is synthetic.

**Status:** accepted (2026-09-16).

## 1. Client scenario

**Who they are.** Kestrelmoor Rail Systems designs, installs and maintains railway signalling and train-control equipment
for urban transit operators (about 2,400 employees, eleven maintenance depots). *Client continuity:
Episode 03 is a direct architectural consequence of Episode 02, inside one system the learner already knows.*

**Where they are now.** Kestrelmoor's internal knowledge assistant answers staff questions from company documents. Its
authorisation architecture — per-section eligibility from current grants and owner classification, enforced inside the
search and re-checked before generation — is in pilot use (the Episode 02 engagement, taken here as the baseline). The
pilot has gone well enough that the COO wants the assistant in every depot, including night shifts, where technicians
use it at the start of a job to check procedures.

**What they want now.** An assistant whose answers can be trusted to reflect the documents *as they are today*: the
current revision of a procedure, the latest safety bulletin, the current classification, and nothing that has been
withdrawn.

## 2. Business problem

**The index is a copy, and copies fall behind.** The records system is the authority for every document's content,
version, status, effective date, classification and retention. The assistant does not answer from the records system; it
answers from a retrieval index built from it. Every time an owner revises, supersedes, withdraws, reclassifies or deletes
a document, the index is wrong until something updates it — and today nobody can say how wrong, for how long, or whether
an update happened at all.

**The week that stopped the rollout (pilot review).**
- **A superseded procedure answered as current.** An engineering safety bulletin withdrew the points-machine inspection
  procedure *MP-114 rev C* after a near-miss and replaced it with a new procedure document, *MP-121*, which changes the
  isolation step. Two days later, a night-shift technician asked the assistant how to isolate a points machine. The
  answer quoted MP-114 rev C. The pre-generation check passed: MP-114's record still existed, with the same label, scope
  and version — it had only been marked *superseded by MP-121*, a status the assistant never reads. A supervisor caught
  it at the job briefing.
- **A current procedure that could not be answered.** In the same week, the owner published *rev E* of a signal-lamp
  replacement procedure. The assistant's check correctly withheld answers from the rev D chunks, because the version no
  longer matched. But the nightly indexing run had failed part-way through; rev E was not indexed for three days, and
  nothing alerted anyone. Depot staff got "I can't answer that right now" for the procedure they needed, and some went
  back to printed copies of unknown age.
- **Content that should be gone.** A supplier contract ended with an obligation to remove the supplier's proprietary
  maintenance manuals from Kestrelmoor systems within an agreed period. The documents were deleted in the records system.
  Answers stopped quoting them — but their chunks and embeddings were still in the index weeks later, and no one could
  show where else derived copies lived.
- **Over-blocking that outlived its reason.** Safety Investigations released a sanitised findings summary to all staff
  by lowering its classification. The index kept the stricter label for three weeks, so the summary stayed invisible to
  the staff it was released for.

**Why it matters.**
- **Safety:** in a maintenance organisation, a superseded procedure presented as current is a safety hazard, not a
  quality defect.
- **Trust:** withheld answers during an unmonitored lag push staff back to uncontrolled copies — the problem the
  assistant was meant to remove.
- **Obligations:** contractual and data-protection deletion must reach *every* derived copy, and Kestrelmoor must be able
  to show it did.
- **Security:** every change pipeline is also a path that could make restricted content retrievable, even briefly.
- **Evidence:** safety assurance and internal audit will ask *when* a bulletin became effective in the assistant.
  Today there is no answer.

**Central architecture question:** how does a retrieval index remain a faithful, provably current derived copy of
authoritative records — as documents are revised, superseded, withdrawn, reclassified and deleted — and what must the
assistant do, and be able to prove, while it is not?

**In one line:** the authorisation is current; the index is not. Keeping the index current is an architecture, not a
nightly job.

## 3. Objectives

| ID | Objective |
|---|---|
| OBJ-1 | Answers reflect the currently effective version of authoritative documents; superseded or withdrawn content is never presented as current guidance |
| OBJ-2 | Every authoritative change reaches the assistant within an agreed, measured window for its change class |
| OBJ-3 | While the index is behind, the assistant behaves safely and honestly — and that behaviour has a bounded duration, not an indefinite one |
| OBJ-4 | Deleted content is removed from every derived copy within its obligation window, with evidence |
| OBJ-5 | Freshness is observable and provable: at any moment the platform can show how far behind the index is, and which changes are pending or failed |
| OBJ-6 | No change, retry, rebuild or repair weakens the Episode 02 authorisation guarantees, even transiently |

## 4. Stakeholders

| Stakeholder | Cares about |
|---|---|
| Chief Operating Officer (sponsor) | Company-wide rollout, including night shifts; no repeat of the superseded-procedure incident |
| Head of Engineering Knowledge (product owner) | Useful, current answers; not withholding more than necessary |
| Head of Engineering Safety | A withdrawn or superseded procedure is never answered as current once the bulletin is effective |
| Records Manager | The records system stays the single authority for versions, status, effective dates, classification and retention |
| Depot Maintenance Managers | Technicians get the current procedure at the start of a job, at any hour |
| Depot technicians and engineers (end users) | An answer they can act on — or an honest "not available yet" — never an out-of-date one presented as current |
| Procurement and Commercial Director | Supplier documents removed within the contractual window after a contract ends |
| Data Protection Officer | Erasure reaches every derived copy of personal data within Kestrelmoor's policy window |
| Chief Information Security Officer | Reclassification and deletion propagate safely; no change path widens eligibility; only the ingestion path writes to the index |
| Head of Safety Investigations | Sanitised summaries become available when released, and restricted material never lingers |
| Internal Audit and Safety Assurance | Evidence of when each change became effective in the assistant |
| Platform team (six engineers) | A change pipeline they can operate, reprocess and trust without routine full rebuilds or constant firefighting |

## 5. Current state → target state

| | Current state | Target state |
|---|---|---|
| Change detection | A nightly indexing run over recently modified documents; failures visible only in run logs | Every authoritative change is detected, applied or visibly failed; nothing is silently lost |
| Supersession and withdrawal | Status is recorded in the records system and ignored by the assistant | A superseded or withdrawn document is not answered as current from the moment its status is effective |
| New versions | Old chunks withheld by verification until the next successful run; no bound on the window | The new version replaces the old within a stated window; answers never mix versions |
| Reclassification | Upward: withheld from the next request (Episode 02). Downward: stays stricter until re-indexed, unbounded | Both directions propagate within stated windows, with no transient widening |
| Deletion | Records deleted; derived copies (chunks, embeddings, other stores) not tracked | Deletion reaches every derived copy within its obligation window, with content-free evidence |
| Freshness evidence | None | Lag by change class, oldest pending change and failed changes are measured, alerted and reportable |
| Recovery | Full re-index is the only repair and takes days | Targeted reprocessing and reconciliation; a full rebuild is possible without stopping answers |

## 6. Requirements that drive the architecture

Defined with IDs in [REQUIREMENTS.md](../02-requirements/REQUIREMENTS.md). The few that shape everything:
- **FRS-002 (INVARIANT):** nothing superseded, withdrawn or deleted is answered as current once that status is effective
  in the authoritative record — whether or not the index has caught up.
- **FRS-004 (INVARIANT):** every change is applied or recorded as failed; no change is silently lost.
- **FRS-005 (INVARIANT):** late, duplicate or out-of-order changes never reinstate an older version, label or deleted
  document.
- **FRS-003:** no answer mixes sections from two versions of the same document.
- **DATA-001:** deletion reaches every derived copy within its window, with evidence.
- **SEC-001 (INVARIANT, inherited):** no change path makes ineligible content retrievable, even transiently.
- **FRS-008:** freshness is measured per change class.

## 7. Scale and change-volume assumptions

Stated as assumptions with rationale, in [ASSUMPTIONS_AND_CONSTRAINTS.md](../02-requirements/ASSUMPTIONS_AND_CONSTRAINTS.md)
(ASM-001 … ASM-012). No invented number is presented as fact. These values belong to this fictional engagement and exist
to force architectural trade-offs; they are not benchmarks or industry requirements.

## 8. Constraints

See [ASSUMPTIONS_AND_CONSTRAINTS.md](../02-requirements/ASSUMPTIONS_AND_CONSTRAINTS.md) (CON-001 … CON-008). In short:
- **Authorities stay put:** the records system remains the authority; the index is derived and must be rebuildable.
- **Baseline:** the Episode 02 authorisation architecture is kept; its invariants are not relaxed.
- **Operations:** answering continues through night shifts, so change processing and rebuilds cannot stop answers.
- **Delivery:** six engineers, company-wide rollout within two quarters; no new manual steps for document owners.

## 9. Risks

| ID | Risk | Why it matters |
|---|---|---|
| RSK-01 | A superseded or withdrawn procedure is answered as current | Checks that compare only label, scope and version pass for a document that is still valid but no longer in force |
| RSK-02 | Changes are silently lost (failed runs, missed events, partial batches) | The index drifts with no signal; containment turns into unmonitored unavailability or stale answers |
| RSK-03 | Out-of-order or duplicate changes reinstate an old version, label or deleted document | Retries and replays are normal; a naive "last write wins" can move the index backwards |
| RSK-04 | An answer mixes sections from two versions of the same document | Old and new chunks coexist during a replacement |
| RSK-05 | Deleted content persists in embeddings, caches, evaluation sets or backups beyond its obligation | "Deleted in the records system" is not "deleted everywhere" |
| RSK-06 | A change, rebuild or repair transiently widens eligibility | Content written before its label, or a rebuild with wrong labels, recreates the Episode 02 disclosure risk |
| RSK-07 | Containment becomes over-blocking | Withholding is safe for a while; unbounded, it drives staff to uncontrolled copies |
| RSK-08 | Bursts of change breach freshness windows | A safety bulletin, a reclassification campaign or a records migration changes thousands of documents at once |
| RSK-09 | No evidence of when a change became effective in the assistant | Safety assurance and audit questions cannot be answered |
| RSK-10 | Full rebuilds become the routine fix | They hide pipeline defects, take days, and compete with answering |
| RSK-11 | Document content manipulates the pipeline | Text claiming "this document supersedes MP-114" must never be treated as an authoritative status change |

## 10. Deliverables

At this gate: the architecture brief, requirements, assumptions and constraints, architecture decision questions and
proposed validation themes (this draft).

After approval of the definition: the options analysis, architecture decision records, target architecture with the
freshness invariants, threat model for the change path, validation plan with deliberate failure experiments,
traceability — then, only when separately authorised, an educational implementation, validation evidence, cost and
cleanup guidance, and portfolio evidence of the work performed.

## 11. Out of scope

- **Tenant isolation:** Episode 01.
- **The authorisation model:** Episode 02's model is the baseline and is not redesigned; this engagement only requires
  that change processing preserves it.
- **Query traffic, quotas, throttling and back-pressure for the answering API:** Episode 04 (change bursts are in scope
  only for their effect on freshness).
- **Cost optimisation of indexing and re-embedding:** Episode 05 (cost is stated as a constraint here, not optimised).
- **Audit evidence and provenance at scale:** Episode 06 (this engagement defines freshness and deletion evidence only).
- **Behaviour when the model is unavailable:** Episode 07.
- **Content correctness:** owners remain responsible for what their procedures say.
- **Answering historical "as of" questions from superseded versions:** out of scope . History is kept
  only where the architecture needs it as evidence, never as a learner-facing answering capability.
- **Legal advice:** contractual and data-protection windows are stated as Kestrelmoor's own policy and contract positions.
