<!-- template: tla-architecture-review/1 -->
# Architecture Review Questions — Kestrelmoor Knowledge Assistant

**Status:** accepted (2026-09-15).

Questions an architecture review board or an interviewer should be able to ask at the end of this engagement. Answer by
citing your artifacts.

| Area | Question | A strong answer cites |
|---|---|---|
| Concepts | Every user is authenticated and every document is the company's. Why is that not enough? | Authorization model §1; SEC-006; the pilot incident in the brief |
| Concepts | Distinguish identity, entitlement, ownership, classification and retrieval eligibility — which one does the retrieval boundary evaluate? | Authorization model §1 and §3; CTL-001 |
| Model | Why not give senior staff a clearance level? What would an operations director then see? | ADR-001 alternatives; SEC-006; TST-ELG-006 |
| Model | Why are department and job title deliberately not authorization inputs? | ADR-001; CTL-001; RR-07 |
| Classification | Where does a section's label come from, and why can't the assistant infer it from the text? | ADR-003; DATA-002; CON-002; TST-DATA-003 |
| Classification | A project report is INTERNAL with a CONFIDENTIAL pricing section. Walk through ingestion and a query by an engineer | ADR-003 decision 4; CTL-008; TST-ELG-004 |
| Classification | What happens to an unlabelled or misspelt label — and why is quarantine better than a default? | DATA-005; CTL-007; TST-DATA-001, TST-DATA-002; RR-08 |
| Minimisation | Why are medical details never indexed, even for the assigned investigator? | ADR-003 decision 3; DATA-004; CMP-001; TST-DATA-004 |
| Enforcement | Why two search tiers here, when Episode 01 chose one shared structure? What would make you choose one index? | ADR-004 rationale; options D2 vs D3 |
| Enforcement | Show every place a domain or case value could enter the retrieval constraint. Which ones are trusted? | CTL-003, CTL-011, CTL-013; TST-SEC-002 |
| Enforcement | Two requesters are both routed to the restricted tier. Why does that not give either of them the other's case? | ADR-004 "The tier is not the authorization boundary"; CTL-012; TST-ELG-009 |
| Failure | The entitlement registry is down. Why does the assistant refuse even INTERNAL questions instead of degrading? | NFR-003; ADR-002; CTL-004; TST-SEC-005; RR-12 |
| Enforcement | Why is filtering chunks after retrieval not the boundary, and why does the design still check chunks after retrieval? | Options D4; ADR-005 rationale; TST-SEN-001 |
| Change | A bid manager leaves the Orion team at 10:00. When do they stop seeing the pricing section, and what bounds that? | ADR-002; SEC-010; ASM-005; TST-CHG-001; TST-SEN-003 |
| Change | A section is reclassified upward but not yet re-indexed. What does an employee see, and what does it cost? | ADR-005; SEC-011; TST-CHG-002; RR-04 |
| Responses | Why must "cannot answer" look the same whether restricted content exists or not? | FUN-003; CTL-016; TST-ELG-008 |
| Audit | What would you need to explain why an employee saw a section, and what must never be in that record? | ADR-006; CTL-018, CTL-020; TST-OBS-001, TST-OBS-002 |
| Evidence | How do you know your eligibility tests can detect a broken boundary, a corrupted label and a stale entitlement? | Validation plan §4; TST-SEN-001, TST-SEN-002, TST-SEN-003 |
| Limits | What does this architecture not protect against? | RR-01 (labels enforced, not validated), RR-03 (inference), RR-05 (privileged path) |
| Next | Which problem does this design hand to the knowledge-base lifecycle? | Residual risk register, final section; RR-04 |
