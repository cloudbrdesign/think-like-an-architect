# Validation Plan — Kestrelmoor Knowledge Assistant: keeping the knowledge base current

**Status:** accepted themes (2026-09-16). This plan says what validation must show; the lab (`../README.md`) and `../EVIDENCE_SUMMARY.md`
show what was observed.

**Principle:** the ten themes are kept in full, and the validation plan is not weakened because an implementation option is
hard to test.

**Principle (Season 1, unchanged):** a test is evidence only if it can fail. Every invariant gets a deliberate failure
experiment in a separate throwaway deployment, with the normal system passing before and after.

## Proposed validation themes

| Theme | What must be shown | Requirements |
|---|---|---|
| VT-1 Supersession and withdrawal | A superseded or withdrawn procedure is never answered as current from its effective time — including before the index is updated, and including when the document's label, scope and version are unchanged | BUS-001, FUN-002, FRS-002, SEC-004, DATA-003 |
| VT-2 Version replacement | During and after a new version, no answer mixes versions; citations name the version used; answers resume within the window | FUN-001, FUN-002, FUN-003, FRS-003 |
| VT-3 Ordering, duplicates and replay | Replaying changes late, twice or out of order leaves the index equal to the authoritative records; nothing older is reinstated | FRS-005, FRS-006 |
| VT-4 Lost change detection | Dropped change notifications are detected by reconciliation, repaired and alerted | FRS-004, FRS-007, OPS-001, OPS-002 |
| VT-5 Partial failure | A failure part-way through change processing leaves no silent loss, no widened eligibility, and a visible, retryable failure | FRS-004, SEC-001, SEC-003, OPS-001 |
| VT-6 Deletion propagation | A deleted document is absent from every derived copy in the inventory within its window, with content-free evidence | FRS-002, DATA-001, DATA-004, CMP-001, CMP-002, SEC-005 |
| VT-7 Reclassification in both directions | Upward takes effect from the next request (Episode 02 regression); downward takes effect only once effective in the record, then within its window | SEC-001, SEC-002 |
| VT-8 Freshness measurement | Reported lag equals injected delays (non-vacuous); window breaches alert; pending windows are bounded and reported | FUN-003, FRS-001, FRS-008, NFR-003, OPS-003 |
| VT-9 Burst and rebuild | A bulletin-sized burst meets its windows at the assumed scale; a rebuild runs while answering continues | BUS-003, DATA-002, NFR-001, NFR-002, OPS-002 |
| VT-10 Episode 02 regression | The Episode 02 eligibility suite passes during and after change processing, retries, reconciliation and rebuild | SEC-001, CON-002 |

## Behaviours the validation must demonstrate (2026-09-16)

The architecture options analysis settled behaviours the themes above must now test explicitly:

| Decision | What validation must show |
|---|---|
| **Known stale is not current** | Once authority says a newer version is effective, the previous version is **withheld** — never served with a currency notice. VT-2 asserts the withhold, and that no answer presents a known-old revision as current |
| **Four candidate states** (ADR-002) | Known current, known pending, known superseded/withdrawn/deleted and unknown are distinguishable, and only "known current" is served. VT-1, VT-2 and VT-7 each exercise a different state |
| **Authority wins on disagreement** (ADR-001) | Where derived state and the record differ, the record decides and the derived state is repaired — VT-1, VT-4 |
| **Watermark semantics** (ADR-007) | The watermark advances only through a completed reconciliation pass; a dropped notification never advances it; overdue reconciliation stalls it visibly and triggers conservative mode — VT-4, VT-8 |
| **Convergence state unavailable** | Safety-critical content fails closed; other content continues only where the request-time check still establishes currency; the outage remains observable and weakens the freshness claim — VT-5 |
| **Reconciliation cadence is measured, not assumed** | The validation environment demonstrates that an overdue reconciliation is detectable; cadence numbers come from measurement, not from this plan |
| **Rebuild demonstration** | At educational scale: current serving generation → build new generation → verify → atomically promote → retire old generation, with answering continuing throughout and the Episode 02 suite passing before promotion — VT-9, VT-10 |
| **Rebuild is exceptional** | The demonstration must not imply that routine full rebuilds are the normal freshness mechanism — VT-9 |

## Failure experiments

**Approved headline experiments: FX-1 (why index freshness alone cannot satisfy FRS-002), FX-2 (older state returning unless application is monotonic) and FX-3 (delivery is not completeness)** — a deliberate teaching progression: status → ordering → loss and
reconciliation. **FX-4 is kept as a required validation theme (VT-6), not a headline experiment.** The exact faults are
designed with the architecture; nothing is implemented yet.

| Candidate | What would be broken | What must then fail |
|---|---|---|
| FX-1 | The assistant ignores the authoritative status of a document (supersession not an input) | VT-1: the superseded procedure is answered as current — incident 1 reproduced |
| FX-2 | Change application ignores authoritative order (last arrival wins) | VT-3: a replayed older version or label is reinstated |
| FX-3 (intellectual peak) | Notifications are dropped **and** reconciliation is disabled | VT-4: lost changes go undetected and no alert fires — incident 2 reproduced. It separates "every received event was processed" from "every authoritative change is accounted for" |
| FX-4 (theme, not headline) | Deletion removes index entries but not one other derived copy | VT-6: the deleted content survives in the derived-copy surface — incident 3 reproduced |

## Traceability

**Chain** (unchanged Season 1 model): requirement → decision → control → test → observed result → evidence.

**At this gate:**
- every requirement names a validation theme or `review`;
- decisions, controls and tests are added at the next gates.
