<!-- template: tla-architecture-review/1 -->
# Architecture Review Questions — keeping the Kestrelmoor knowledge base current

Questions an architecture review board or an interviewer should be able to ask at the end of this engagement. Answer by
citing your artefacts and what you saw in the lab.

| Area | Question | A strong answer cites |
|---|---|---|
| Concepts | The index is rebuilt from the records system. Why is it still wrong for part of every day? | Brief; ADR-001; the lab's Part A |
| Concepts | Name the four states a retrieval candidate can be in. Why is only one of them served, and why is an age not a state? | ADR-002; the four-state card |
| Currency | A withdrawn document's copy is still in the index and matches on label, scope and version. What refuses it, and where? | FRS-002; ADR-002; CTL-030; lab A4–A5 |
| Currency | Why is re-checking label and scope at request time (Episode 02) not enough to catch a withdrawal? | FRS-002; BUS-001; lab A5 |
| Completeness | Notifications fire within seconds. Why can they never prove that the index is complete? | ADR-003; FRS-007; the two-lane diagram |
| Completeness | State the watermark definition exactly. What may advance it, and to which moment? | ADR-003; ADR-007; the watermark definition |
| Completeness | Reconciliation compared 15 documents and found nothing. When is that result evidence, and when is it not? | ADR-003; reconciliation over an empty index |
| Ordering | A late notification for version 1 arrives after version 2 has been applied. What stops the index going backwards? | FRS-005; FRS-006; ADR-004 |
| Replacement | How do you stop an answer mixing sections from two versions of the same document? | FRS-003; ADR-005 |
| Deletion | Authority deletes a document. What does "deleted from the index" have to mean, and how is it evidenced? | ADR-006; DATA-003 |
| Retention | A withdrawn procedure is kept in the records system for history. Why is it still never retrievable? | DATA-003; lab A7 |
| Failure | A change cannot be applied. Walk through what the system records, retries and escalates, and when | FRS-004; OPS-001; the escalation contract; lab B4–B7 |
| Failure | Why must a retry never reset the incident's clock? | ADR-007 §3; lab B7 |
| Failure | Why does removing the fault not, on its own, apply the change? | ADR-003; ADR-008; lab B8–B9 |
| Operations | The alarm is still raised after the repair. Is that a defect? | The alarm's one-hour evaluation period; lab B10 |
| Operations | Reconciliation has not run for over an hour. What should the assistant do, and why is that not an outage? | ADR-002; ADR-007; the overdue check |
| Windows | Why does an upward reclassification get a zero-second window, but a new version four hours? | FRS-001; the window table |
| Evidence | How would you show that your reconciliation detects a change that was never delivered? | 06-validation/VALIDATION_PLAN.md; lab Part A |
| Limits | What does this architecture not protect against? | Residual risks; the authority itself being wrong |
| Transfer | Where else in your estate is a copy trusted because it is present? | Your own architecture note |
