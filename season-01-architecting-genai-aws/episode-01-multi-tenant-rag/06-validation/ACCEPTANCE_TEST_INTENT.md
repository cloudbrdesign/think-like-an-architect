# Acceptance Test Intent — Veltamere Document Assistant

These are **behavioural outcomes** the finished system must demonstrate. They are not implementation-specific tests yet:
the architecture stage turns them into a validation plan with concrete setup, actions and evidence.

## Principles

1. **Deployment is not validation.** A system that deploys has proven nothing about isolation.
2. **Negative tests are mandatory.** Every boundary has an attempt that must be refused.
3. **A control that has never been observed failing proves little.** At least one sensitivity test deliberately removes or
   disables the isolation control in a controlled test condition and confirms the negative tests then **fail**
   (TST-SEN-011). The disabled condition is never part of anything that ships.
4. **No vacuous passes.** A cross-tenant test asks for content that **does exist** in the other tenant and would be
   retrieved if the boundary were absent. TST-SEN-011 demonstrates that.
5. **Every output channel counts.** "Blocked" means the other tenant's information appears nowhere: retrieval results,
   generated answer, citations, source metadata, and any record or cache the learner can inspect.
6. **Decide at the boundary.** Leakage is judged primarily at the point where content is retrieved. A model's answer not
   repeating something does not prove it was not retrieved. Checks on generated answers are repeated, and any leak fails.
7. **Synthetic data only.**

## Synthetic test data (intent)

- **Tenant A** and **Tenant B** are fictional facilities-management companies with documents on the **same topics** (for
  example, a cleaning services contract with different rates), so a cross-tenant question has a real target.
- Each tenant's documents contain a **unique marker phrase** that occurs nowhere else. Detecting the other tenant's marker
  anywhere in an output is an unambiguous leak.
- A third synthetic tenant (Tenant C) is used to test onboarding.

## Test intents

| ID | Verifies | Intent | Required outcome |
|---|---|---|---|
| TST-ISO-001 | FUN-001, FUN-002 | A Tenant A user asks about Tenant A's documents | **ALLOWED** — answer grounded in and citing Tenant A's documents |
| TST-ISO-002 | FUN-001, FUN-002 | A Tenant B user asks about Tenant B's documents | **ALLOWED** |
| TST-ISO-003 | SEC-001, SEC-004, DATA-002, CMP-001 | A Tenant A user asks for information that exists only in Tenant B's documents | **BLOCKED** — no Tenant B marker in any output channel |
| TST-ISO-004 | SEC-001, SEC-004, DATA-002, CMP-001 | A Tenant B user asks for information that exists only in Tenant A's documents | **BLOCKED** |
| TST-SEC-005 | SEC-003 | A user authenticated for Tenant A supplies Tenant B's identifier in every caller-controllable field | **BLOCKED** — tenant context is unchanged; no Tenant B information |
| TST-SEC-006 | SEC-005 | A Tenant A user's question instructs the assistant to ignore its rules and use Tenant B's documents | **DOES NOT CROSS THE RETRIEVAL BOUNDARY** — nothing from Tenant B is retrieved |
| TST-SEC-007 | SEC-002 | A request with no valid authenticated identity | **BLOCKED** — no retrieval, no generated answer |
| TST-SEC-008 | SEC-005 | A Tenant A document contains hostile instructions to reveal other tenants' information; a Tenant A user asks about it | **DOES NOT CROSS THE RETRIEVAL BOUNDARY** |
| TST-SEC-009 | SEC-009 | Attempt to reach documents or retrieval data by any path that avoids the authorisation decision | **BLOCKED**, or the path is shown to lie outside the trusted path and to be unavailable to tenant users |
| TST-ASM-010 | SEC-006, DATA-003 | A document carrying Tenant B's marker is attributed to Tenant A (simulated mis-attribution) | **DETECTED, PREVENTED, QUARANTINED, OR EXPLICITLY EXPOSED AS A RESIDUAL RISK** — the expected outcome is fixed by the architecture before the test runs |
| TST-SEN-011 | SEC-001, SEC-004 | With the isolation control deliberately disabled in a controlled test condition, run TST-ISO-003 and TST-ISO-004 | **BOTH MUST FAIL** — proving the negative tests can detect a leak |
| TST-OPS-012 | OPS-004 | Run cleanup, then search for remaining resources | **VERIFIABLE** — no billable resources remain |
| TST-SEC-013 | SEC-008 | Tenant context or authorisation data is missing, malformed or unresolvable | **BLOCKED** — no retrieval results (fail closed); the event is recorded |
| TST-DATA-014 | FUN-003 | A tenant deletes a document; ask about it after the agreed window | The document and its derived data are **no longer retrieved** |
| TST-OPS-015 | OPS-001, CMP-001 | Inspect the records produced by TST-ISO-003 and TST-SEC-013 | An investigator can identify user, tenant context, decision and outcome; **no document content** in the records |
| TST-DATA-016 | BUS-001 | A tenant with the assistant disabled | Its documents are **never retrieved** and not processed for retrieval |
| TST-OPS-017 | BUS-002, NFR-002 | Enable Tenant C using the documented procedure, then run the isolation tests across A, B and C | **No code change or per-tenant rule needed**; all isolation tests pass |
| TST-OPS-018 | OPS-003, OPS-005 | From a fresh copy of the published instructions, deploy non-interactively and run the automated isolation tests | Deployment **reproducible**; tests run **unattended** |
| TST-SEC-019 | SEC-006, DATA-001 | A Tenant A user uploads a document while trying to assign it to Tenant B (any field or embedded value) | Attributed to **Tenant A** or **refused**; the ownership record shows owner, uploader, time and status |
| TST-SEC-020 | SEC-007 | Attempt to change a document's owning tenant through a user-facing path | **REFUSED**; any administrative correction is recorded |
