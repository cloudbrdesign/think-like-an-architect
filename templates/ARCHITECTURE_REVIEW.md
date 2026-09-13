<!-- template: tla-architecture-review/1 -->
# Architecture Review — <engagement title>

Answer as if an experienced reviewer were challenging you. Cite your artifacts; defending the architecture matters more
than recalling facts.

| Area | Question | A strong answer cites |
|---|---|---|
| Decisions | Why this architecture? | Requirements, options analysis |
| Decisions | Which requirement drove each major decision? | ADRs, traceability matrix |
| Decisions | Which alternatives did you reject, and why? | Options analysis |
| Enforcement | Where exactly is each key control enforced? | Diagrams (`ENFORCES:` labels), ADR controls |
| Enforcement | What happens if an input the control relies on is wrong? | Threat model, assumption tests |
| Scale and failure | What fails first at scale? | Assumptions, cost and capacity notes |
| Risk | What is the largest residual risk? | Threat model residual risks |
| Context change | What would change for a more regulated or sensitive context? | Requirements, threat model |
| Assurance | How would you prove this control to an auditor? | Tests, evidence, traceability matrix |
| Production | What would production require beyond this implementation? | Teaching simplifications, cost notes |
