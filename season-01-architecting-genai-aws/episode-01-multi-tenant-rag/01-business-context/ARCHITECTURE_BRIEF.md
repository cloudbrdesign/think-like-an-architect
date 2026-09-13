<!-- template: tla-architecture-brief/1 -->
# Architecture Brief — A Document Assistant for Veltamere Facilities Cloud

> **Fictional scenario for learning.** Veltamere Facilities Cloud and every customer described here are invented; any
> resemblance to a real organisation is coincidental. This brief describes the problem. It deliberately does not describe
> a solution.

**Engagement:** TLA-S01E01 · **Stage:** engagement design — the architecture is not yet decided

---

## 1. Client scenario

**Veltamere Facilities Cloud** is a business-to-business software platform for **facilities-management companies** — the
firms that clean, maintain and secure office buildings, hospitals, warehouses and campuses on behalf of property owners.

| | |
|---|---|
| **Business model** | Annual subscription per customer organisation, priced by the number of sites the customer manages |
| **Customers (tenants)** | About 120 facilities-management companies (ASM-001), from regional firms with a few dozen staff to national providers with thousands. **Many of them compete for the same contracts.** |
| **Users** | Each customer's contract managers, site managers and supervisors; each customer's own administrators; Veltamere support staff |
| **Why multi-tenancy exists** | Veltamere runs **one shared platform** for all customers. Each customer is a tenant. A five-engineer platform team could not operate a separate platform per customer, and the subscription price assumes shared infrastructure |
| **Documents** | Service contracts and pricing schedules · supplier price lists and rate cards · site safety procedures and permits · equipment maintenance manuals · incident reports |

Those documents are the most commercially sensitive information a facilities-management company holds. A competitor
seeing a customer's contract rates, supplier discounts or incident history could undercut that customer on its next bid.

## 2. Business problem

Veltamere's customers store thousands of documents on the platform but struggle to **use** them. A site supervisor who
needs to know whether a contract allows weekend call-outs, or what the lock-out procedure is for a specific chiller, must
search by keyword and read long documents on a phone. Customers routinely say they cannot find answers they already own,
and two competitors now advertise conversational search.

Veltamere wants its customers' staff to **ask questions in natural language and receive answers grounded in, and citing,
their own organisation's documents.**

The existing keyword search is insufficient: it matches words rather than meaning, cannot combine information across
documents, and returns documents rather than answers.

**What makes this an architecture problem rather than a feature:** the answers are generated from retrieved document
content. If retrieval ever draws on another customer's documents, the platform has disclosed one competitor's confidential
information to another. Customer contracts require logical segregation of each customer's data (section 9). A single
confirmed cross-customer exposure would likely mean contract breaches, notification obligations, lost customers and a halt
to the product's sales.

## 3. Business objectives

| Objective | Statement | Observable signal | Realised through requirements |
|---|---|---|---|
| OBJ-1 | Staff can ask natural-language questions and receive cited answers from **their own organisation's** documents | Pilot users answer a set of real questions from their own documents faster than with keyword search | FUN-001, FUN-002, FUN-003 |
| OBJ-2 | A new customer can be enabled for the assistant **without deploying or hand-configuring a separate platform** | A tenant is enabled through a repeatable procedure with no code change | BUS-001, BUS-002, NFR-002 |
| OBJ-3 | **No customer's information reaches another customer** — not in retrieval, answers, citations or metadata | Cross-tenant tests are refused, and the tests are shown capable of failing | SEC-001 to SEC-009, DATA-002 |
| OBJ-4 | Veltamere can **investigate** a suspected exposure: who asked, in which tenant context, what was decided, what was retrieved | An investigator reconstructs any query's access decision and retrieved documents from records | OPS-001, OPS-002 |
| OBJ-5 | Running cost grows with **usage**, so the assistant fits existing subscription tiers | The cost model shows no large fixed cost per added tenant unless a decision justifies it | NFR-004, CON-002 |
| OBJ-6 | Veltamere can **show customers and their auditors** that isolation is tested, not assumed | Test results and audit evidence can be produced on request | CMP-001, OPS-005 |

## 4. Stakeholders

Only stakeholders whose concerns change the architecture are listed.

| Role | Concern | Architectural consequence |
|---|---|---|
| Chief Product Officer (business owner) | Adoption and competitive parity; fast onboarding of customers | Isolation must not require per-customer projects; answers must be useful enough to adopt |
| Head of Platform Engineering | A small team with no dedicated on-call for a new product | Prefers few moving parts; every additional per-tenant component is an operational cost |
| Security Lead (part-time) | Cross-customer leakage; forged tenant context; proving what happened | Authorisation before retrieval; fail closed; investigable access records; testable controls |
| Customer administrators (the data owners) | Their confidential documents; contractual segregation; what happens when they delete a document or leave | Clear document ownership; deletion and disablement must stop retrieval; evidence of isolation |
| Legal and contracts | Confidentiality and segregation clauses; exposure notification; hosting region commitment | Isolation stated as an invariant; audit trail; data stays in the contracted region |
| Customer staff (end users) | Fast, trustworthy answers they can verify | Citations to the source document; latency; citations must only ever point to their own documents |

## 5. Current state

Only facts that shape the design are recorded. They describe today's platform, not the future assistant.

- **Application:** one web application and one set of backend services serve all tenants from a single deployment.
- **Identity:** users sign in through Veltamere's existing identity provider. It issues signed session tokens containing
  the user's identifier and their tenant membership. Some larger customers sign in through their own corporate single
  sign-on, federated into the same identity provider. A small number of users (for example consultants) belong to more
  than one tenant and switch between them.
- **Documents:** uploaded files are kept in a shared file store under a per-tenant folder path. Document records live in
  a shared relational database with a tenant identifier column. Documents are therefore **logically** separated, not
  physically.
- **Tenant scoping today:** most document endpoints take the tenant from the user's session. **A legacy export endpoint
  accepts a tenant identifier as a request parameter** and checks it against the session; a past penetration test flagged
  that pattern as fragile.
- **Search:** keyword search queries the database, scoped by the tenant identifier column.
- **Audit:** logins and document uploads are logged. **Searches are not logged.**
- **Operations:** five platform engineers and one site reliability engineer; a part-time security lead; no out-of-hours
  support for new features during a pilot.

## 6. Target state

Capabilities the platform must have after this engagement — not services or components.

- One shared platform serves the assistant to every enabled tenant.
- Every question comes from an authenticated user, and the user's tenant context is established by a trusted part of the
  system.
- Authorisation is decided before any document content is retrieved, and retrieval is constrained to the authorised
  tenant's documents.
- Every document and everything derived from it carries its owning tenant, assigned by a trusted part of the system.
- Answers cite their source documents, and citations only ever refer to the user's own tenant.
- Access decisions and retrievals are recorded well enough to investigate an incident, without copying document content
  into logs.
- Enabling a new tenant is repeatable and requires no code change or hand-written per-tenant rule.
- The isolation boundary is testable, and the tests are shown capable of detecting a failure.

## 7. Requirements

Requirements, with stable IDs and the security invariants, are in
[REQUIREMENTS.md](../02-requirements/REQUIREMENTS.md).

## 8. Scale, availability and performance

All figures are **assumptions** unless stated otherwise, recorded with their consequences in
[ASSUMPTIONS_AND_CONSTRAINTS.md](../02-requirements/ASSUMPTIONS_AND_CONSTRAINTS.md):
about 120 tenants today, growing towards 400 in two years (ASM-001); from a few hundred to about 50,000 documents per
tenant (ASM-002); a few thousand questions per day at general availability (ASM-003).

## 9. Compliance and contractual context

This engagement is not a compliance exercise. Only the obligations that shape the architecture are included.

- Customer master agreements require **confidentiality** and **logical segregation** of each customer's data.
- Customers may request **evidence of security controls** once a year.
- Veltamere must **notify** a customer promptly of any suspected exposure of its data.
- Contracts commit that customer data is **hosted in a single named region**.
- Incident reports can contain names of staff. In this episode, **all tenant documents are treated as confidential tenant
  data**; finer classification of personal and sensitive information is the subject of Episode 02.

No specific regulation is claimed.

## 10. Constraints

See [ASSUMPTIONS_AND_CONSTRAINTS.md](../02-requirements/ASSUMPTIONS_AND_CONSTRAINTS.md) (CON-001 to CON-009). The
constraints that create the sharpest trade-offs: a shared platform with a small team (CON-002, CON-003), the existing
identity provider remains authoritative (CON-004), a single hosting region (CON-006), and a reproducible, low-cost learner
implementation (CON-007, CON-008).

## 11. Risks

See [INITIAL_RISK_REGISTER.md](../03-architecture/INITIAL_RISK_REGISTER.md). None of the risks is mitigated yet.

## 12. Deliverables of this engagement

| Deliverable | Stage |
|---|---|
| Brief, requirements, assumptions, constraints, risks, decision questions, acceptance intent, traceability seed | Engagement design (this stage) |
| Options analysis, architecture decision records, diagrams, threat model, validation plan | Architecture |
| Learner implementation, validation results including refused cross-tenant attempts, cleanup | Implementation and validation |
| Portfolio evidence of the work performed; architecture review | Evidence |

## 13. Out of scope

Each of these is named once and taught in its own episode: detailed classification and protection of sensitive and
personal information (Episode 02) · keeping document knowledge current, including full deletion propagation (Episode 03) ·
designing for production traffic and quotas (Episode 04) · cost optimisation (Episode 05) · audit evidence design
(Episode 06) · behaviour when a model or dependency is unavailable (Episode 07).

## 14. Questions the architecture must answer

See [ARCHITECTURE_DECISION_QUESTIONS.md](../04-decisions/ARCHITECTURE_DECISION_QUESTIONS.md).
