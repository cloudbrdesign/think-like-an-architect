<!-- template: tla-architecture-review/1 -->
# Architecture Review Questions — Veltamere Document Assistant

The questions an architecture review board or an interviewer should be able to ask you at the end of this engagement.
They are published now so they shape your design from the start. Answer by citing your artifacts; defending the
architecture matters more than recalling facts.

| Area | Question | A strong answer cites |
|---|---|---|
| Decisions | Which requirement drove your tenant isolation model? | Requirements, DQ-A options analysis, ADR |
| Decisions | Why did you choose logical or physical isolation — and what would make you change it? | Options analysis, assumptions ASM-001, ASM-002 |
| Identity | Where is tenant identity trusted, and why is that component trustworthy? | DQ-B decision, identity flow diagram |
| Identity | Why can't a user change their tenant? Show the path a forged tenant identifier takes | SEC-003, TST-SEC-005 result |
| Authorisation | Where exactly does authorisation occur, and what happens if that component receives no tenant context? | DQ-C decision, SEC-008, TST-SEC-013 result |
| Authorisation | Is there any path to the documents that does not pass authorisation? How do you know? | SEC-009, TST-SEC-009 result, threat model |
| Retrieval | What happens if a user asks the model for another tenant's data — and which control actually stops it? | SEC-005, TST-SEC-006 result, retrieval boundary diagram |
| Retrieval | Why is removing other tenants' content after retrieval not good enough? | SEC-004 |
| Data | What happens if ingestion metadata is wrong? Who could make it wrong? | SEC-006, DATA-003, TST-ASM-010 result |
| Evidence | How do you know your cross-tenant tests are not passing vacuously? | TST-SEN-011 result, RSK-14 |
| Risk | What is the largest residual risk in your design? | Threat model, risk register |
| Scale | What fails first as the tenant count grows towards 400? | Assumptions, cost model, NFR-002 |
| Context change | What would change if the documents were regulated or highly sensitive data? | Requirements, Episode 02 scope |
| Assurance | How would you prove tenant isolation to a customer's auditor? | CMP-001, test results, access records |
| Production | What would production require beyond the learner implementation? | Teaching simplifications, operations and cost notes |
