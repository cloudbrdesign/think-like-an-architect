<!-- template: tla-implementation-controls/1 -->
# Implementation Controls — keeping the knowledge base current

**Stage:** implementation · **Status:** built, not yet validated against AWS · **Date:** 2026-09-16

Episode 02's controls CTL-001 … CTL-029 are inherited **unchanged** and are documented in
[Episode 02's control catalogue](../../episode-02-sensitive-data-rag/05-implementation/IMPLEMENTATION_CONTROLS.md). This file
documents only what Episode 03 adds.

Each control names the code that implements it, the place a permission expresses it (where one does), and the test that
would notice if it were removed. A control with no test that can fail is not a control.

## CTL-030 — Authoritative status confirmation at request time

| | |
|---|---|
| **What it does** | Before generation, every candidate's authoritative record is read and its lifecycle status checked. Superseded, withdrawn, deleted, not-yet-effective and invalid records are discarded. |
| **Why** | FRS-002 is an externally observable safety property, not a statement about index latency (ADR-002). Episode 02 checked label, scope and version — all of which are unchanged when a document is superseded. |
| **Code** | `core/record_state.py` (parses the record), `core/verification.py` (currency checked **first**, before the Episode 02 checks), `query/handler.py` step 6a. |
| **Outcome codes** | `WITHHELD_NOT_CURRENT`. |
| **Removing it** | Its validation tests fail. FX-1 removes it deliberately. |

## CTL-031 — Convergence state as an answering input

| | |
|---|---|
| **What it does** | Each candidate is classified `KNOWN_CURRENT`, `KNOWN_PENDING`, `KNOWN_SUPERSEDED_WITHDRAWN_DELETED` or `UNKNOWN`. Only `KNOWN_CURRENT` may be served. A known-old revision is withheld, never served with a notice. When completeness cannot be proven for a safety-critical class, the request is withheld rather than answered on an unprovable claim. |
| **Why** | ADR-002: known stale is not current. A warning banner is not a safety control. |
| **Code** | `core/convergence.py`, `core/freshness.py` (`conservative_mode`), `query/handler.py` step 6b. |
| **Outcome codes** | `WITHHELD_PENDING_CHANGE`, `WITHHELD_UNKNOWN_STATE`, `WITHHELD_CONVERGENCE_UNAVAILABLE`. |
| **Direction** | This control can only ever **withhold**. It never makes content available that eligibility would have refused (SEC-001; §16). Its validation tests check that direction explicitly. |
| **Removing it** | Its validation tests fail. |

## CTL-032 — Monotonic, idempotent change application

| | |
|---|---|
| **What it does** | A change applies only when its authoritative version is newer than the version derived state reflects, or when the status changed at the same version. Duplicates are no-ops; older arrivals and post-deletion changes are recorded as refused, never applied. **The same rule governs PROMOTION, not just the incremental apply:** no path may make a generation serving if doing so would move derived state backwards. `may_promote()` is defined in terms of the same decision, so there is one definition of monotonicity — allowed for `APPLY` and `DUPLICATE`, refused for `OLDER` and `AFTER_DELETE`. |
| **Why** | FRS-005 and FRS-006: retries, replays and reconciliation repairs make out-of-order arrival normal. AB-14: monotonicity is an invariant over **transitions of derived state**, not a feature of one caller — the rebuild path reached the switch without the ordering decision and moved a document from v2 back to v1. |
| **Code** | `core/change_apply.py` (`decide`, `may_promote`), `change/applier.py`, enforced at `core/generations.py` (`switch`). |
| **Removing it** | Its validation tests fail. FX-2 removes it deliberately — and now removes it from **every** promoting path, which is what the invariant means. |

## CTL-033 — Generations and the switch

| | |
|---|---|
| **What it does** | A document's derived content is written as a complete generation keyed by its authoritative version, verified (every expected section present, each carrying this document, section and version), then switched in one write. The previous generation is retired afterwards. A failed build leaves the previous generation serving and the document pending. |
| **Why** | FRS-003: no answer may mix two versions of a document, including during replacement. |
| **Code** | `core/generations.py`, `change/applier.py` (`_build_and_switch`), `change/rebuild.py`. |
| **The promotion boundary** | `generations.switch()` is the one place a generation becomes the serving one, so it is where the monotonic invariant is enforced for every path at once (CTL-032, AB-14). It takes the currently-serving state as a **required** argument, read at switch time, and refuses a promotion that would move derived state backwards — removing the generation it just built rather than leaving copies behind. A caller cannot promote without stating what it is replacing. |
| **Removing it** | Its validation tests fail. |

## CTL-034 — Deletion across the derived-copy graph

| | |
|---|---|
| **What it does** | Deletion walks the graph this implementation actually creates — section objects, knowledge-base documents, vector entries, generation records, pending entries — and records a content-free ledger entry naming what was proven removed. The entry reaches the physical phase only when **every** kind is proven removed. |
| **Why** | DATA-001, DATA-004, CMP-001, CMP-002. "Retrieval no longer returns it" is not deletion (§11). |
| **Code** | `core/deletion.py`, `change/applier.py` (`_remove`). |
| **Permission** | Only `ChangeRole` may delete index documents or section objects (template). |
| **Removing it** | Its validation test fails. FX-4 is kept as a validation theme (VT-6) rather than a headline experiment. |

## CTL-035 — Change detection and completeness

| | |
|---|---|
| **What it does** | Two mechanisms, deliberately separate: the records table's stream gives a low-latency signal that writes a pending entry before any content work; reconciliation compares the authoritative export with derived state and produces missing, extra and divergent sets, repairs them, and is the **only** thing that may advance a watermark — to the moment the pass **started**, never to "now". |
| **Why** | FRS-004 and FRS-007. Change delivery is not proof of completeness: a change that was never delivered is invisible to delivery. |
| **Code** | `change/notifier.py`, `change/reconciler.py`, `adapters/stores.py` (`advance_watermark`). |
| **Permission** | `NotifierRole` may write only `PENDING#` keys; `ChangeRole` may write every derived prefix **except** `WATERMARK#`; only `ReconcilerRole` may write a watermark (template). |
| **Removing it** | Its validation tests fail. FX-3 removes it deliberately, together with the notifications. |

## CTL-036 — Freshness evidence

| | |
|---|---|
| **What it does** | Records, per answer and system-wide: the authoritative version confirmed, the proven watermark per change class, the global conservative floor, the limiting class, the pending count and oldest pending age, the age of the last completed reconciliation, whether each class is inside its window, and the claim the evidence actually supports. Queue depth and last-successful-job time are reported separately and labelled as **operational metrics, not freshness proof**. |
| **Why** | ADR-007: processing latency is not provable freshness. |
| **Code** | `core/freshness.py`, `core/audit_record.py` (`freshness_entry`, schema `tla-e03-audit/1`). |
| **Removing it** | Its validation tests fail. A measurement that cannot detect an injected delay is not evidence. |

## What the controls do not do

- They do not decide **who may see what**. Eligibility remains Episode 02's, evaluated inside the search and verified
  before generation (CTL-011 … CTL-014). Every Episode 03 control can narrow an answer; none can widen one.
- They do not make the index authoritative. Derived state that disagrees with the record is repaired, never believed.
- They do not promise an index latency. They promise that content whose currency cannot be established is not served.
