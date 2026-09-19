# Assumptions and Constraints — Kestrelmoor Knowledge Assistant: keeping the knowledge base current

**Status:** working assumptions (2026-09-15).

An **assumption** is believed true but not confirmed. Each names what changes if it is false. A **constraint** is a
condition the architecture must work within, listed because it forces a trade-off.

## Assumptions

| ID | Assumption | Why it matters to the architecture | If false, then | Validate by |
|---|---|---|---|---|
| ASM-001 | About 180,000 documents (carried from the Episode 02 engagement), about 2,400 users after company-wide rollout (**ASSUMPTION**) | Corpus size bounds rebuild and reconciliation time | Rebuild and reconciliation estimates change | Records Manager's library inventory |
| ASM-002 | About 3,000 document changes per working day in steady state (new versions, status changes, reclassifications, deletions) (**ASSUMPTION**) | Daily volume sizes change processing | Windows may not hold, or the design is oversized | Records-system change report over 90 days |
| ASM-003 | The records system can notify changes as they happen, at least once, **possibly duplicated, out of order, or missed during its own outages**; it can also produce a complete export of current records (**ASSUMPTION**) | Delivery properties decide whether events alone are enough and whether reconciliation is required | If only exports exist, change detection becomes comparison-based and windows lengthen; if notifications are exactly-once and ordered, some safeguards simplify | Records-system integration review |
| ASM-004 | Engineering safety bulletins are issued a few times a month; one bulletin can supersede or withdraw up to about 50 procedures. A reclassification campaign or records migration can change up to about 20,000 documents at once (**ASSUMPTION**) | Bursts test windows and ordering | Burst sizing is wrong | Head of Engineering Safety; Records Manager |
| ASM-005 | Every record carries a version that increases with each change, an effective-from time and a status (in force, superseded, withdrawn, deleted); supersession names the replacing document (**ASSUMPTION**) | Ordering and supersession need authoritative version and status data | Ordering must be inferred, and supersession cannot be enforced mechanically | Records-system data model review |
| ASM-006 | Supplier contracts require removal of the supplier's proprietary documents from Kestrelmoor systems within 30 days of contract end (**ASSUMPTION**; contract position owned by Procurement) | Sets the supplier-deletion window | The deletion window changes | Procurement confirms contract terms |
| ASM-007 | Kestrelmoor's data-protection policy requires approved erasures to reach derived copies within 30 days (**ASSUMPTION**; policy position set by the DPO, not legal advice) | Sets the erasure window | The erasure window changes | DPO confirms policy |
| ASM-008 | Indexing one document takes seconds to minutes; rebuilding the whole corpus takes days (**ASSUMPTION** — to be measured) | Separates targeted reprocessing from full rebuilds | Rebuild-based repair may be viable, or even targeted repair may be too slow | Measurement in the educational implementation |
| ASM-009 | Backups of derived stores are retained for about 35 days (**ASSUMPTION**) | Deletion obligations must account for backups | The backup position in DATA-001 changes | Platform team backup policy |
| ASM-010 | The Episode 02 authorisation architecture is in pilot use as designed, including per-request grants and pre-generation verification against the current record (label, scope and version) | It is the baseline this engagement must preserve and extend | The baseline must be re-established first | Episode 02 engagement and evidence |
| ASM-011 | Night-shift technicians use the assistant at the start of a job; about a quarter of questions arrive outside office hours (**ASSUMPTION**) | Rules out maintenance windows for answering | Scheduled downtime could be acceptable | Pilot usage data |
| ASM-012 | The learner implementation uses a synthetic organisation, synthetic people and synthetic documents only | No real personal data, secrets or customer information | — | Stated fact for the learner implementation |

## Constraints

| ID | Constraint | Consequence for the architecture |
|---|---|---|
| CON-001 | The records system remains the single authority for content, versions, status, effective dates, classification and retention | The index is derived and rebuildable; the assistant never becomes a second authority |
| CON-002 | The Episode 02 authorisation architecture is the baseline; its invariants are not relaxed | Every freshness mechanism must preserve eligibility during and after change |
| CON-003 | Six-person platform team with business-hours support and an escalation rota, not a dedicated 24×7 ingestion team | Failures must be visible, self-describing and safely retryable |
| CON-004 | Answering continues around the clock; there is no maintenance window for the assistant | Reprocessing and rebuilds cannot stop answers |
| CON-005 | Company-wide rollout within two quarters | Scope must stay proportionate; routine full rebuilds cannot be the plan |
| CON-006 | No new manual steps for document owners beyond what the records system already asks of them | Change signals must come from existing records data |
| CON-007 | Re-embedding and re-indexing carry time and cost; full rebuilds are exceptional (cost optimisation itself is Episode 05) | Targeted change processing is preferred; rebuild is the fallback, not the method |
| CON-008 | Educational implementation: synthetic data only; the learner deploys into their own sandbox and cleans up | The design must be demonstrable at small scale with failure experiments |
