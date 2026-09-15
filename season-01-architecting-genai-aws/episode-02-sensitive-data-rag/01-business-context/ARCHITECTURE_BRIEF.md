<!-- template: tla-architecture-brief/1 -->
# Architecture Brief — Kestrelmoor Knowledge Assistant

> Fictional scenario for learning. Kestrelmoor Rail Systems, its people, projects, cases and documents are invented.
> All engagement data is synthetic.

**Status:** accepted (2026-09-15).

## 1. Client scenario

**Who they are.** Kestrelmoor Rail Systems designs, installs and maintains railway signalling and train-control equipment
for urban transit operators. It has about 2,400 employees (ASM-001) across:
- engineering;
- project delivery and bids;
- eleven maintenance depots;
- finance;
- HR;
- safety investigations;
- a small security engineering team that assesses vulnerabilities in the company's own signalling products.

**What they want.** Kestrelmoor wants one internal knowledge assistant, used by any employee, that answers questions from
the company's own documents with citations. Today that knowledge is spread across departmental libraries in the
company's document management system (the records system).

## 2. Business problem

**Everything is legitimate, and access still isn't uniform.** Every user is an authenticated employee, and every document
belongs to Kestrelmoor. But access to the information inside those documents is not uniform:
- **Project reports:** a delivery report contains lessons every engineer should read — and a section holding the bid
  pricing for a live tender.
- **Safety investigations:** a report has a sanitised findings summary for all staff, witness statements for the assigned
  investigators only, and medical details that no assistant use case needs at all.
- **HR case files:** open only to the case owner.
- **Vulnerability assessments:** the signalling products' assessments are need-to-know within security engineering.

**The pilot that was stopped.** A six-week internal pilot indexed two departments' shared folders with folder permissions
flattened to "all staff". In internal testing, an answer about depot safety quoted a paragraph from a witness statement
in an open investigation, naming a colleague. It was contained before any wider rollout, but the pilot was stopped.
- **The lesson:** a knowledge assistant that is less careful than the records system turns every legitimate user into a
  potential disclosure path.
- **What could follow:** harm to named employees, a data-protection incident, a compromised investigation, a leaked
  tender price or a published product weakness.

## 3. Objectives

| ID | Objective |
|---|---|
| OBJ-1 | Staff find authoritative engineering, procedural and project knowledge faster than through departmental search (measured by pilot survey and task timing) |
| OBJ-2 | No employee receives information they are not entitled to — including sections of documents whose other sections they may read |
| OBJ-3 | Sensitive personal information (HR, safety investigations, medical details) is never easier to reach through the assistant than through the records system |
| OBJ-4 | Every answer and every refusal can be explained after the fact, without the audit trail becoming a new copy of sensitive content |
| OBJ-5 | Changes to who may see what — people joining or leaving teams, documents being reclassified — are honoured without an engineering change |

## 4. Stakeholders

| Stakeholder | Cares about |
|---|---|
| Chief Operating Officer (sponsor) | Faster engineering and depot work; no repeat of the pilot incident |
| Head of Engineering Knowledge (product owner) | Useful answers for all staff; not over-blocking the INTERNAL material that is most of the value |
| Records Manager | Classification labels stay owned by document owners in the records system; the assistant must not become a second classification authority |
| Data Protection Officer | Minimal processing of employee personal data; special-category data (for example medical information) never processed without need |
| Chief Information Security Officer | Fail-closed behaviour; no route around authorization; security-sensitive product information stays need-to-know |
| Head of Safety Investigations | Witness statements visible only to assigned investigators; investigations never compromised |
| HR Director | HR case files visible only to the assigned case owner |
| Commercial Director | Live bid pricing visible only to the bid team |
| Security Engineering Lead | Vulnerability assessments visible only to the security engineering compartment |
| Employee representatives | Staff personal data is not exposed, and monitoring of staff through audit logs is proportionate |
| Platform team (six engineers) | A design they can operate and change; no per-case engineering |
| Employees (end users) | Honest answers; no hint that restricted material exists when they cannot see it |

## 5. Current state → target state

| | Current state | Target state |
|---|---|---|
| Finding knowledge | Departmental library search; knowledge siloed | One assistant answering from everything the employee is entitled to, and nothing else |
| Classification | Owners assign labels in the records system to about 70% of documents (ASM-003); section marking exists for three high-risk document types (ASM-004) | Owner-assigned labels, at document and section level, drive eligibility. Unlabelled content is not indexed until labelled |
| Access decisions | Folder permissions in the records system; project, case and compartment grants held in the entitlement registry | The same authoritative entitlement sources decide what each question may retrieve, at the moment it is asked |
| Pilot | Stopped after the witness-statement exposure | Relaunch for about 300 pilot users (engineering, projects, safety) within one quarter (CON-006) |

## 6. Requirements that drive the architecture

Defined with IDs in [REQUIREMENTS.md](../02-requirements/REQUIREMENTS.md). The few that shape everything:
- **SEC-001:** nothing from a section the employee is not eligible for, in any output channel.
- **SEC-006:** authenticated is not eligible; seniority never substitutes for need-to-know.
- **SEC-004:** eligibility is decided before retrieval.
- **DATA-002 and DATA-003:** labels come from the owner's classification record, and chunks never outrank or out-scope their section.
- **DATA-004:** special-category personal data is never indexed.
- **SEC-007:** fail closed on unresolved entitlements or invalid labels.

## 7. Scale, availability and performance assumptions

Stated as assumptions with rationale, in [ASSUMPTIONS_AND_CONSTRAINTS.md](../02-requirements/ASSUMPTIONS_AND_CONSTRAINTS.md)
(ASM-001 … ASM-010). No invented number is presented as fact.

## 8. Constraints

See [ASSUMPTIONS_AND_CONSTRAINTS.md](../02-requirements/ASSUMPTIONS_AND_CONSTRAINTS.md) (CON-001 … CON-008). In short:
- **Authorities stay put:** the records system keeps classification authority, the identity provider keeps identity, and
  the entitlement registry keeps grants.
- **Delivery:** a six-person platform team; a pilot within one quarter.
- **Archive:** no whole-archive re-marking before the pilot.

## 9. Risks

| ID | Risk | Why it matters |
|---|---|---|
| RSK-01 | Sensitive sections inherit a document's broader label | Mixed-sensitivity documents are common; a document-level label would expose the most sensitive section |
| RSK-02 | Owners mislabel content at the source | The architecture enforces labels, not truth |
| RSK-03 | Revoked access keeps working | People move between bids, cases and teams constantly |
| RSK-04 | Reclassified content keeps being served from the index | The index is a copy; the classification record is the authority |
| RSK-05 | Senior staff assume they may see everything | Need-to-know is not seniority; the organisation's culture may push against it |
| RSK-06 | Audit logs become a new sensitive dataset | Logging questions or excerpts would copy restricted content into operational systems |
| RSK-07 | Over-blocking makes the assistant useless | INTERNAL knowledge is most of the value; quarantining unlabelled content removes about 30% of the corpus at first |
| RSK-08 | Answers reveal that restricted material exists | "You are not allowed to see the Orion pricing" is itself a disclosure |
| RSK-09 | Many entitlements make access decisions large or slow | Some employees hold dozens of project and case grants |

## 10. Deliverables

Requirements, authorization and sensitivity model, threat model, options analysis, architecture decision records, target
architecture with a stated security invariant, validation plan with deliberate failure experiments, traceability. After
approval: an educational implementation, validation evidence, cost and cleanup guidance, and portfolio evidence of the
work performed.

## 11. Out of scope

- **Tenant isolation between organisations:** Episode 01. Kestrelmoor is one organisation.
- **Ingestion freshness, deletion propagation and index synchronisation:** Episode 03. This engagement names the
  consequences of change (section 5 of the authorization model) and designs only what authorization requires.
- **Traffic management, cost optimisation, audit evidence at scale and model-outage behaviour:** Episodes 04–07.
- **Legal advice:** data-protection obligations are stated as Kestrelmoor's own policy requirements, set by its Data
  Protection Officer.
- **Generating or correcting classification labels:** owners remain responsible (CON-002). Automated detection is
  evaluated only as an advisory aid.
