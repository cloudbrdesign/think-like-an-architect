# Authorization and Sensitivity Model — Kestrelmoor Knowledge Assistant

**Status:** accepted (2026-09-15).

**Purpose:**
- Separate five concepts that are easy to blur: identity, authorization, ownership, sensitivity and retrieval eligibility.
- Answer the questions that drive the requirements.
- Record the model that ADR-001 to ADR-006 propose.

---

## 1. Five concepts that must not be used interchangeably

| Concept | Question it answers | Authoritative source | What it is **not** |
|---|---|---|---|
| **Identity** | Who is asking? | Workforce identity provider, via a verified token (SEC-002) | Not permission. Being authenticated grants nothing beyond INTERNAL eligibility, and even that requires active employment |
| **Authorization (entitlement)** | What is this person explicitly allowed to see? | HR system (employment status) and the entitlement registry (domain memberships, case assignments) (SEC-003) | Not a token claim, a job title, a department or seniority (SEC-006) |
| **Ownership** | Whose document is it? | Kestrelmoor owns every document | Decides nothing here. This is the Episode 01 question, and here it has one answer |
| **Sensitivity (classification)** | How damaging is disclosure, and to whom is it scoped? | The owner's classification record in the records system, per document and per marked section (DATA-002) | Not the document's text, folder, file name or a model's opinion |
| **Retrieval eligibility** | May *this* person retrieve *this* section *now*? | Decided per request by the policy decision point, from entitlements and classification (ADR-002) | Not a stored permission list. It is computed from the two authorities at the moment of the request |

**The whole episode in one relation:** eligibility = f(current entitlements of the requester, current classification of
the section). The model is not an input, and the question text is not an input.

---

## 2. Sensitivity taxonomy (derived from the scenario)

| Label | Meaning | Scope | Who is eligible | Handling |
|---|---|---|---|---|
| **INTERNAL** | General company knowledge: standards, procedures, sanitised investigation findings, lessons learned | None | Any active employee | Answers may be cached per label (deferred to Episode 05); normal content-free audit |
| **CONFIDENTIAL** | Disclosure harms a business function or product: bid pricing, finance packs, vulnerability assessments | Exactly one **access domain** (for example `BID-ORION`, `FIN-REPORTING`, `SEC-SIGNALLING`) | Active employees who are members of that domain | No answer caching; no excerpts outside the answer; content-free audit |
| **RESTRICTED** | Disclosure harms named people or an investigation: HR case files, witness statements | Exactly one **case** (for example `HR-2031`, `SI-0417`) | Active employees assigned to that case — nobody else, whatever their seniority | Restricted tier only; no caching; content-free audit |
| *special-category mark* | Medical and similar special-category personal data | — | **Nobody through the assistant** | **Never indexed** (DATA-004). It is not a retrievable label |

**Why not a clearance ladder?** A ladder (for example INTERNAL < CONFIDENTIAL < RESTRICTED, with seniors cleared "up to
RESTRICTED") would let an operations director read any HR case. Kestrelmoor's rules are compartments plus need-to-know:
- the security engineering lead may see vulnerability assessments but not HR cases;
- an HR caseworker may see their own case but not bid pricing.

Labels express how sensitive something is; **scopes** express who needs it. That is decision question DQ-A, proposed in
ADR-001.

**Effective label of a chunk:** the section's label and scope. If a section is unmarked, the document's label and scope
apply. A section can never be less restrictive than its document (DATA-003). A chunk never crosses a section boundary.

---

## 3. The eligibility rule (ADR-001, CTL-001)

```
eligible(requester, section) =
    requester.employment_status == ACTIVE                        (from the HR system, now)
  AND (   section.label == INTERNAL
       OR (section.label == CONFIDENTIAL AND section.domain ∈ requester.domain_memberships)   (registry, now)
       OR (section.label == RESTRICTED   AND section.case   ∈ requester.case_assignments) )   (registry, now)
  AND section.label, section.scope are valid under DATA-001        (otherwise: not eligible, recorded)
```

**Inputs the rule never reads:** department, job title, grade, seniority, token group claims, anything in the request
body or headers, the question text, document text.

---

## 4. The driving questions, answered by the proposed model

| Question | Proposed answer | Where decided |
|---|---|---|
| Who is the requester? | The employee identified by the verified token | Edge (CTL-002) |
| What organisation do they belong to? | Kestrelmoor — one organisation. There is no tenant decision in this engagement | — |
| What role or attributes do they have? | Only three attributes matter: employment status, domain memberships, case assignments. Role and grade are deliberately **not** authorization inputs | Policy decision point (CTL-003) |
| What documents are potentially relevant? | Whatever search ranks as relevant — but only *eligible* sections are ever candidates | Retrieval, inside the search (CTL-011, CTL-012) |
| Which documents are they authorised to access? | The question is wrong in this engagement. Eligibility is decided per **section**, and a document can be partly eligible | Eligibility rule (CTL-001) |
| Does authorization apply to the whole document or to portions? | To marked sections. Unmarked documents fall back to the document label (ASM-004, CON-007) | Ingestion (CTL-008) |
| Where does classification come from? | The owner's classification record in the records system; never from text (DATA-002) | Ingestion (CTL-006) |
| Who is authoritative for authorization? | The HR system (status) and the entitlement registry (grants). The assistant holds no permission list of its own | Policy decision point (CTL-003) |
| When is the authorization decision made? | At every request, before retrieval (SEC-004) | Policy decision point, then gateway |
| What happens when authorization changes? | The next request after the registry records the change is decided on the new grants (SEC-010). Registry lag is ASM-005 | Per-request resolution (CTL-003) |
| What happens when classification changes? | Upward: the pre-generation check compares with the current record and withholds (SEC-011). Downward: stays at the old, stricter label until re-indexed — the safe direction. Propagation timing is Episode 03 | Verification (CTL-014); re-indexing (RR-04) |
| What happens when metadata is missing? | The section is excluded from the index and reported (DATA-005). At query time, a chunk without a valid label is ineligible | Ingestion (CTL-007); verification (CTL-014) |
| What happens when metadata is malformed? | The same: a label outside the taxonomy, or a label/scope mismatch, is invalid → excluded and reported | Ingestion (CTL-007) |
| What if retrieval returns something outside the authorised scope? | The whole answer is withheld, a security event is recorded, and the response is indistinguishable from "cannot answer" | Verification (CTL-014, CTL-016) |
| What must be logged? | Employee identifier, entitlement and classification record versions used, decision, labels and scope identifiers of retrieved and withheld chunks, outcome, timings (SEC-012, OPS-002) | Audit (CTL-018) |
| What must **not** be logged? | Document content, excerpts, answer text, question text (a keyed hash only), special-category content in any form | Audit and logging (CTL-018, CTL-019) |
| What does fail-closed mean here? | Unresolvable entitlements or an unavailable authoritative source → **no retrieval at all**, a safe uniform failure and a content-free audit event (no authoritative current grants = no retrieval). Invalid label → not retrievable. A decision too large to represent → refuse, never truncate. Verification mismatch → withhold everything | CTL-004, CTL-007, CTL-013, CTL-014 |

---

## 5. Consequences of change (named here; freshness design is Episode 03)

| Change | Effect on eligibility | Handled in this engagement by | Left for Episode 03 |
|---|---|---|---|
| Employee removed from a domain or case | Ineligible from the next request once the registry records it | Per-request resolution | Registry propagation guarantees (ASM-005) |
| Employee leaves the company | Nothing beyond refusal: an inactive status fails everything | HR status in the rule | — |
| Section reclassified upward | Newly ineligible users are withheld even while the index holds the old label | Pre-generation verification | Re-index timing; the withheld-answer rate while the index is stale |
| Section reclassified downward | Stays restricted to the old scope until re-indexed | Safe by design | Propagation window |
| Section boundaries change in a new document version | Old chunks keep old boundaries until re-indexed | Verification against the current record's section version | Version-aware re-indexing |
| Section or document deleted | Chunks remain until removal completes | Verification finds no current record → ineligible | Deletion propagation |
