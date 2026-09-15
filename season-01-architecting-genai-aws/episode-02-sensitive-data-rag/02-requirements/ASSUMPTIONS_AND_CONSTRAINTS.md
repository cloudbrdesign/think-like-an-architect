# Assumptions and Constraints — Kestrelmoor Knowledge Assistant

**Status:** accepted (2026-09-15).

An **assumption** is believed true but not confirmed. Each names what changes if it is false. A **constraint** is a
condition the architecture must work within, listed because it forces a trade-off.

## Assumptions

| ID | Assumption | Why it matters to the architecture | If false, then | Validate by |
|---|---|---|---|---|
| ASM-001 | About 2,400 employees and about 180,000 documents. The pilot has about 300 users from engineering, projects and safety (**ASSUMPTION**) | Volume shapes index topology and ingestion | Scale choices may not hold | Records Manager's library inventory |
| ASM-002 | About 150 access domains (departments, projects, bids, security compartments) and about 400 open RESTRICTED cases. Most employees hold 0–5 entitlements; a few hold up to about 40 (**ASSUMPTION**) | The size of each eligibility decision drives how it can be enforced inside search | Larger entitlement sets may not fit a search-time constraint; the design must fail closed (NFR-002) | Entitlement registry export |
| ASM-003 | Owner-assigned labels exist for about 70% of documents; the rest are unlabelled (**ASSUMPTION**) | Unlabelled content is excluded (DATA-005), which limits early value | Coverage lower than expected makes the pilot less useful; a labelling programme is needed | Records system report |
| ASM-004 | Section-level marking already exists for safety investigation reports, project reports with commercial sections, and vulnerability assessments; other document types are marked at document level only (**ASSUMPTION**) | Section granularity depends on marking that owners already produce | Mixed documents without section marks must be treated at their most restrictive document label | Records Manager confirms marking practice |
| ASM-005 | The entitlement registry reflects a data owner's revocation within 15 minutes of the owner's action (**ASSUMPTION**) | Bounds how quickly SEC-010 can take effect end to end | Revocation lags beyond what owners expect | Registry owner confirms the synchronisation schedule |
| ASM-006 | Special-category content is identifiable from existing records-system marking (for example a "medical" section mark) (**ASSUMPTION**) | Minimisation (DATA-004) must be enforced mechanically | Unmarked medical content could be indexed; an advisory detection step becomes necessary | Sample of investigation and HR documents |
| ASM-007 | A few thousand questions per day at pilot peak (**ASSUMPTION**) | Load bounds the cost and latency of per-request entitlement resolution | Per-request resolution may need a short-lived cache, which changes revocation timing | Pilot measurement |
| ASM-008 | The identity provider's token identifies the employee reliably. Its group claims can be up to one token lifetime (about one hour) out of date (**ASSUMPTION**) | This is why entitlements are not taken from token claims (SEC-003) | If claims were always current, the entitlement lookup could be simplified | Identity provider owner confirms token lifetime and claim refresh |
| ASM-009 | Changes to classification records are versioned and readable by the assistant (**ASSUMPTION**) | Verification against the current record (SEC-008, SEC-011) needs a readable record and version | Verification can only use the indexed label; stale labels are not caught | Records system integration review |
| ASM-010 | The learner implementation uses a synthetic organisation, synthetic people and synthetic documents only | No real personal data, secrets or customer information | — | Stated fact for the learner implementation |

## Constraints

| ID | Constraint | Trade-off it creates |
|---|---|---|
| CON-001 | Season 1 is implemented on AWS | Options are evaluated in one cloud environment; the reasoning must not depend on a particular service |
| CON-002 | The records system remains the single classification authority; document owners assign labels. The assistant never becomes a second classification authority | Eligibility can only be as correct as owners' labels (RSK-02); no silent "auto-fix" |
| CON-003 | Existing authorities remain: the workforce identity provider for identity, the HR system for employment status, and the entitlement registry for domain memberships and case assignments | The assistant must integrate with these sources rather than build its own access model |
| CON-004 | A platform team of six engineers and a part-time security architect | Every additional store, pipeline or policy engine competes for a small team |
| CON-005 | Documents, derived data and records stay in the single contracted hosting region | Rules out processing elsewhere |
| CON-006 | The relaunched pilot should start within roughly one quarter (**ASSUMPTION** — delivery target) | Favours designs that can be validated quickly without weakening authorization |
| CON-007 | The archive cannot be re-marked before the pilot; section marking exists only where ASM-004 says | Section granularity applies where marks exist; elsewhere the document label governs |
| CON-008 | Educational implementation: synthetic data only; learners deploy into their own sandbox account; resources are cleaned up after each session | The corpus must make authorization failures obvious without real data |
