<!-- template: tla-options-analysis/1 -->
# Architecture Options Analysis — Kestrelmoor Knowledge Assistant

**Status:** accepted (2026-09-15).

Every option below is credible for *some* organisation. Each is judged against Kestrelmoor's requirements, and a rejected
option names the requirement it fails. The decisions are recorded as **proposed** ADRs.

---

## 1. Authorization and sensitivity model — ADR-001

**Decision question:** DQ-A.

| Criterion | From requirement(s) | Why it matters here |
|---|---|---|
| Need-to-know independent of seniority | SEC-006 | HR cases and witness statements are assigned, not ranked |
| Positive access for the entitled | FUN-002 | Over-blocking breaks the product (RSK-07) |
| Changes without engineering | BUS-002, BUS-003 | Grants change daily |
| Section granularity | FUN-004 | Mixed documents are common |
| Decision size at query time | NFR-002 | Some employees hold about 40 grants |

| Option | How it works | Verdict |
|---|---|---|
| **A1 — Hierarchical clearance** | Labels ordered INTERNAL < CONFIDENTIAL < RESTRICTED; each person has a clearance level | **Rejected.** Fails SEC-006: a cleared director sees every case. It cannot express "this bid team only" |
| **A2 — Role and department groups** | Eligibility from department or job-role groups | **Rejected.** Too coarse for case assignment and bid teams; groups drift; fails SEC-006 whenever a role implies sensitive access |
| **A3 — Labels with scopes plus explicit entitlements** | A section has a label and one scope (domain or case). A person has explicit memberships and assignments. Eligibility is computed | **Proposed.** Expresses compartments and need-to-know. The decision stays small (label + scope IDs). Owners grant through the existing registry |
| **A4 — Per-document access lists copied from the records system** | Each chunk carries a list of permitted people or groups | **Rejected.** Document ACLs are per document, not per section (fails FUN-004). Copies drift from the source. Lists of principals per chunk grow with headcount and churn; E01 rejected the same pattern for the same reason |

---

## 2. Classification authority and granularity — ADR-003

**Decision question:** DQ-B.

| Option | Verdict |
|---|---|
| **B1 — Document-level owner labels only** | **Rejected as the whole answer.** Fails FUN-004: a pricing section would force the whole report to CONFIDENTIAL and hide the lessons from everyone. Retained as the fallback when a document has no section marks (CON-007) |
| **B2 — Section-level owner labels from the records system** | **Proposed.** One authority (CON-002), with the granularity mixed documents need. Invalid marks are quarantined (DATA-005) |
| **B3 — Automated classification as the authority** | **Rejected.** Makes the assistant a second classification authority (fails CON-002, DATA-002). Model or pattern errors become authorization errors, silently |
| **B4 — Owner labels authoritative, automated detection as advice** | **Kept as a possible extension, never an authorization source.** A detector that quarantines *suspicious INTERNAL sections* for owner review reduces RR-01 without taking authority. It adds components and false positives |

**Rules that follow from B2:**
- A chunk never spans sections.
- The effective label is never less restrictive than the document label.
- Classification text inside a document is ignored (DATA-002, TST-DATA-003).

---

## 3. Minimisation — ADR-003

**Decision question:** DQ-C.

| Option | Verdict |
|---|---|
| **C1 — Index everything someone could be eligible for** | **Rejected** for special-category content. No use case needs medical details, so indexing them creates risk with no benefit (fails DATA-004, CMP-001) |
| **C2 — Never index special-category content; index RESTRICTED content case-scoped** | **Proposed.** The safest retrieval boundary is data that was never indexed. Assigned investigators and caseworkers keep the use cases they need |
| **C3 — Index only sanitised summaries of RESTRICTED material** | **Not proposed.** It would remove the investigator and caseworker use cases (FUN-002); it remains an option if Kestrelmoor narrows scope |

---

## 4. Retrieval eligibility enforcement and index topology — ADR-004

**Decision question:** DQ-D.

| Criterion | From requirement(s) |
|---|---|
| Ineligible sections never become candidates | SEC-001, SEC-004 |
| Question and content cannot widen scope | SEC-005 |
| No route around the decision | SEC-009 |
| Blast radius of one defect limited for the most harmful content | SEC-013 |
| Correct with large entitlement sets, fail closed otherwise | NFR-002 |
| Operable by six engineers; affordable | CON-004, NFR-004 |

### Option D1 — Separate index per access domain and per case
- **How it works:** one structure per domain (about 150) and per open case (about 400); a query searches the structures
  the person is entitled to.
- **Advantages:** strongest separation; a defect exposes one structure.
- **Disadvantages:**
  - hundreds of structures, created and destroyed as cases open and close;
  - cross-domain questions fan out and merge rankings;
  - a section moving scope means moving data between structures.
- **Verdict:** **rejected** at this scale (CON-004, NFR-004, BUS-003).

### Option D2 — One shared index with a mandatory eligibility constraint
- **How it works:** every chunk carries label and scope; the gateway builds
  `INTERNAL OR (CONFIDENTIAL AND domain ∈ memberships) OR (RESTRICTED AND case ∈ assignments)`, evaluated during search.
- **Advantages:** one structure; simplest ingestion and operations; E01's proven pattern generalised.
- **Disadvantages:** one missing or mis-evaluated clause exposes **everything**, including witness statements and HR cases,
  to every employee.
- **Verdict:** **credible runner-up.** Choose it only if Kestrelmoor accepts shared blast radius for RESTRICTED content in
  exchange for simplicity.

### Option D3 — Sensitivity-tiered indexes, each with a mandatory constraint (proposed)
- **How it works:**
  - a shared tier holds INTERNAL and CONFIDENTIAL chunks, with the constraint
    `INTERNAL OR (CONFIDENTIAL AND domain ∈ memberships)`;
  - a restricted tier holds RESTRICTED chunks and is queried **only** for people with case assignments, with the
    constraint `case ∈ assignments`;
  - only the gateway can query either tier.
- **Advantages:**
  - a defect in the shared constraint cannot expose RESTRICTED content, because it is not there;
  - the restricted tier is reachable by the few people with case assignments, through a separately permissioned path;
  - two structures, not hundreds.
- **Disadvantages:**
  - two retrieval calls for case-assigned users, with rankings merged;
  - ingestion must route correctly (a routing defect is itself a threat, tested by TST-DATA-006);
  - somewhat more to operate than D2.
- **Verdict:** **proposed.** Separate by sensitivity where blast radius justifies it; constrain inside where scale requires
  it.

### Option D4 — Retrieve broadly, then decide eligibility per chunk
- **Verdict:** **rejected as the control** (fails SEC-004). Ineligible content has left the store, entered memory and
  possibly logs. Kept only as **verification** in ADR-005, where it detects but never prevents.

### Option D5 — Prompt instructions ("do not reveal confidential content")
- **Verdict:** **rejected** (fails SEC-005). A model can be persuaded; the content is already in context.

### Option D6 — Redact or scan generated answers
- **Verdict:** **rejected as the control** (fails SEC-004). It acts after generation and cannot see paraphrase or
  inference.

| Criterion | D1 | D2 | D3 | D4 | D5 | D6 |
|---|---|---|---|---|---|---|
| Ineligible never a candidate | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Scope cannot be widened by text | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ |
| Blast radius of one constraint defect | One structure | Everything | One tier (never RESTRICTED from the shared tier) | Everything | Everything | Everything |
| Structures to operate | ~550 | 1 | 2 | 1 | 1 | 1 |
| Cross-domain questions | Fan-out | Native | Native (shared); second call only for case-assigned users | Native | Native | Native |
| Fit for six engineers | ✗ | ✓ | ✓ | ✓ | ✓ | ✓ |

---

## 5. Entitlement source and decision timing — ADR-002

**Decision question:** DQ-E.

| Option | Verdict |
|---|---|
| **E1 — Token group claims** | **Rejected.** Claims can be about an hour stale (ASM-008), so a revoked bid-team member keeps access (fails SEC-010). Token size limits restrict how many grants fit |
| **E2 — Per-request resolution by a policy decision point** | **Proposed.** Status, memberships and cases are read from the authoritative sources for every request, with source versions recorded. Revocation takes effect from the next request after the registry records it |
| **E3 — Periodic entitlement snapshot** | **Not proposed.** Revocation waits for the refresh interval. It is a legitimate optimisation if ASM-007 load makes per-request resolution too slow — a measured decision, not a default |

**Unavailable source:** no retrieval at all. An INTERNAL-only degraded mode was rejected: it would create a
second authorization mode that runs exactly when the authoritative decision cannot be made.

---

## 6. Between retrieval and generation — ADR-005

**Decision question:** DQ-F.

| Option | Verdict |
|---|---|
| **F1 — Trust retrieval** | **Rejected.** Stale labels (SEC-011), tampering and managed-search defects (RR-11) would go undetected |
| **F2 — Re-verify each chunk against the current classification record and the decision; withhold the whole answer on any mismatch** | **Proposed.** A mismatch means a defect or an unpropagated change; withholding makes it visible and prevents partial leakage |
| **F3 — Re-verify and silently drop mismatched chunks** | **Not proposed.** It keeps answers flowing but hides defects, and the answer may still reflect the dropped content's existence |

**Outputs:**
- citations only from verified chunks, at section level;
- a uniform "cannot answer from the content available to you" response;
- no caching of answers built from CONFIDENTIAL or RESTRICTED content.

---

## 7. Audit — ADR-006

**Decision question:** DQ-G.

| Option | Verdict |
|---|---|
| Full request/response logging | **Rejected.** It copies restricted content into logs and monitors staff disproportionately (fails SEC-012) |
| **Content-free decision records with source versions** | **Proposed.** Records decisions, labels, scope IDs, source versions and outcomes. Question text is kept only as a keyed hash |
| No per-request records | **Rejected.** Fails OPS-002 and OBJ-4 |
