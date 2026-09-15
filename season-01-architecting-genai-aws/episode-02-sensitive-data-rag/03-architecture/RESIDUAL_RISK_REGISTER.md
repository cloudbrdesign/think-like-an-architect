# Residual Risk Register — Kestrelmoor Knowledge Assistant

**Status:** accepted (2026-09-15).

**What this register holds:** risks that remain if the proposed architecture works as designed. Each names what would
change the risk and who owns it.

| ID | Residual risk | Why it remains | Owner | What would change it |
|---|---|---|---|---|
| RR-01 | **Labels are enforced, not validated for truth.** A section an owner labels INTERNAL is served to everyone | The assistant is not a classification authority (CON-002). No retrieval control can know the owner meant something else | Records Manager | A labelling review programme; advisory sensitive-content detection that quarantines suspicious INTERNAL sections for owner review |
| RR-02 | **Entitlement data correctness and propagation.** A wrong grant is honoured; a revocation takes effect only once the registry records it (ASM-005) | The registry is authoritative by design | Data owners · registry owner | Registry synchronisation guarantees; periodic access reviews |
| RR-03 | **Aggregation and inference.** Eligible INTERNAL facts can be combined to infer restricted facts | Retrieval eligibility governs content, not inference | DPO · Head of Safety Investigations | Minimisation of what INTERNAL summaries contain; sanitisation guidance for owners |
| RR-04 | **Change propagation windows.** Downward reclassification, new section boundaries in a document version, deleted sections and sanitised summaries that lag their full report persist in the index until re-indexing. Upward changes are withheld by verification, at the cost of withheld answers while the index is stale | The index is a derived copy; this engagement enforces authorization at query time but does not design the knowledge base's lifecycle | Platform team | **Episode 03:** freshness, re-indexing, deletion propagation, versioning and synchronisation |
| RR-05 | **Privileged administrator access** to indexes and stores outside the query path | Operators must be able to run the platform | CISO | Separation of duties; access logging; break-glass procedures |
| RR-06 | **Answer integrity within eligible content.** Injected text in an eligible document can mislead that employee's answer; it cannot widen eligibility | Content is untrusted input; the boundary holds, the answer may still be wrong | Head of Engineering Knowledge | Content provenance and quality controls; user reporting |
| RR-07 | **Pressure for a "senior override".** Organisational demand to let senior staff see everything | Need-to-know is a policy position, not a technical limit | COO · HR Director | Any override becomes an explicit, logged entitlement, never an implicit rule |
| RR-08 | **Unlabelled archive excluded** (about 30%, ASM-003) | Fail-closed labelling (DATA-005) | Records Manager | A labelling programme; owner-approved bulk labelling of general libraries as INTERNAL |
| RR-09 | **Content logging enabled later for debugging** | Operational pressure during incidents | CISO | Configuration drift checks on logging settings |
| RR-10 | **Search-time constraint limits.** Two limits were observed under the tested conditions: the retrieval API rejects constraints above 15,360 bytes (SPK-E02-A), and the vector store behind it rejects constraints above 10,240 bytes of its own form of the filter (build re-measurement: 561 short or 281 long scope IDs accepted; the next one rejected; the last grant honoured by every accepted constraint). The application refuses anything above 8,192 bytes, never truncates; about 40 grants use 926 bytes | Correctness is preferred over availability (NFR-002); the limits are platform properties that can change, and the spike measured only the first of them | Platform team | Re-measure at each build (TST-SCALE-001 checks the largest constraint the application accepts against the service); a decision-splitting design validated for completeness if real grant sets approach the budget |
| RR-11 | **Primary control runs inside a search component the architecture does not own** | Managed search evaluates the constraint | Platform team | Pre-generation verification detects a mis-evaluated constraint before generation (CTL-014) |
| RR-12 | **Availability depends on the authorization sources.** When the entitlement registry or HR system is unavailable, no question is answered at all, including INTERNAL questions | Correctness is preferred over availability; a degraded mode would be a second authorization path | COO · Platform team | Resilience of the authorization sources; failure behaviour is designed in Episode 07 |

## What this engagement leaves to Episode 03 — the next architecture problem

Authorization at query time answers *who may see this section now*. It deliberately does **not** answer the questions
this design exposes:
- **How quickly does a change reach the index?** Reclassifications, revoked sections, deleted documents and new document
  versions.
- **What does the index hold when a document is updated?** Old chunks with old section boundaries and labels.
- **How does verification stay cheap** when many labels are stale at once?
- **How do sanitised summaries stay consistent** with the investigation reports they summarise?
- **How are the records system, the entitlement registry and the index kept in step,** and what is consistent when they
  are not?

These are the concerns of *How to Keep a Production Knowledge Base Up to Date*.
