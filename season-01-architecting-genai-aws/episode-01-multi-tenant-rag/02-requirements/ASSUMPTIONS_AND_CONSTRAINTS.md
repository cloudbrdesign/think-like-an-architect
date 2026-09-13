# Assumptions and Constraints — Veltamere Document Assistant

An **assumption** is something believed true but not yet confirmed. It never silently becomes a guarantee: each one names
what changes if it is false and how it will be validated. A **constraint** is a condition the architecture must work
within; each one is listed because it forces a trade-off.

## Assumptions

| ID | Assumption | Why it matters to the architecture | If false, then | Validate by |
|---|---|---|---|---|
| ASM-001 | About 120 tenants today; a pilot with 5 design-partner tenants; growth towards about 400 tenants within two years (**ASSUMPTION** — sales forecast) | Tenant count drives whether per-tenant structures remain manageable | Isolation and cost choices may not scale, or may be over-engineered | Product confirms the forecast before architecture approval |
| ASM-002 | Documents per tenant range from a few hundred to about 50,000; mostly PDF and word-processor files of 1–300 pages (**ASSUMPTION**) | Volume and skew affect retrieval structure, ingestion time and cost | Very large tenants may need different handling than small ones | Sample of pilot tenants' document inventories |
| ASM-003 | A few thousand questions per day at general availability, with peaks of roughly 15 per minute; about three times that within two years (**ASSUMPTION**) | Load shapes latency and cost trade-offs | Latency or cost targets may be unreachable with the chosen design | Pilot usage measurement |
| ASM-004 | The identity provider's session token identifies the user and **exactly one active tenant** per session; multi-tenant users switch tenant explicitly (**ASSUMPTION**) | Determines where tenant context can be trusted from and how switching is handled | Tenant context may be ambiguous; an additional membership check may be required | Identity provider owner confirms token contents and switching behaviour |
| ASM-005 | Tenant membership data in the identity provider is accurate: a user listed in a tenant genuinely belongs to it (**ASSUMPTION**) | Every tenant boundary — retrieval and ingestion attribution — inherits this correctness | A mis-assigned user is authorised for the wrong tenant, whatever the retrieval design | Customer administrators' membership review process |
| ASM-006 | In the pilot, documents enter only through the platform's authenticated upload feature; no bulk import from customer systems (**ASSUMPTION**) | Limits the ingestion paths that must attribute ownership correctly | Additional ingestion paths need their own trusted attribution | Product confirms pilot scope |
| ASM-007 | Each tenant's documents are private to that tenant; there is **no shared content** intended for all tenants in scope (**ASSUMPTION**) | A shared corpus would create a legitimate cross-tenant retrieval case and change the isolation model | The isolation model must distinguish shared from tenant content | Product confirms; any shared corpus becomes a separate decision |
| ASM-008 | Customers accept that a deleted document may remain retrievable for up to 24 hours before removal completes (**ASSUMPTION** — to be agreed with customers) | Sets how quickly deletion must propagate to derived data | A shorter window changes ingestion and deletion design | Customer administrators and Legal agree the window |
| ASM-009 | The learner implementation uses synthetic tenants and synthetic documents only | No real customer data is ever used for learning or testing | — | Stated fact for the learner implementation |

## Constraints

| ID | Constraint | Trade-off it creates |
|---|---|---|
| CON-001 | Season 1 is implemented on AWS | Options are evaluated within one cloud environment; the architectural reasoning must not depend on a particular service |
| CON-002 | One shared platform. Dedicated infrastructure per tenant is allowed only where a decision justifies it against the requirements | Physical isolation strength versus cost and operational load |
| CON-003 | Five platform engineers, one site reliability engineer, a part-time security lead; no out-of-hours support for the pilot | Every additional per-tenant component or operational process competes with a small team |
| CON-004 | The existing identity provider remains the source of user identity and tenant membership; this engagement does not replace it | Tenant context must be derived from what the identity provider already provides |
| CON-005 | The pilot with five design-partner tenants should start within roughly one quarter (**ASSUMPTION** — delivery target) | Favours designs that can be built and validated quickly without weakening isolation |
| CON-006 | Customer data and anything derived from it stay in the single contracted hosting region | Rules out designs that process or store tenant content in other regions |
| CON-007 | The learner implementation must deploy non-interactively and reproducibly from published instructions, using the simplest mechanism that keeps the isolation control visible and testable | The learner build must reveal the boundary, not hide it in production machinery |
| CON-008 | A complete learner build → validate → cleanup session should cost under **USD 10** (**TARGET** — to be confirmed by a dated estimate during architecture) and leave nothing running | Rules out learner designs with significant always-on costs |
| CON-009 | The assistant is additive: existing document storage and features keep working as they do today | Constrains whether documents are reused in place or copied for retrieval, and how ownership is carried across |
