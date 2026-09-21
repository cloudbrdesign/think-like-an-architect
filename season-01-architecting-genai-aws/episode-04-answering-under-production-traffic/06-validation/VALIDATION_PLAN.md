# Validation Plan — Kestrelmoor Knowledge Assistant: answering under production traffic

**Status:** **APPROVED themes** (2026-09-20); refined at E2 where the architecture gives them precision. Test
IDs, fixtures, load profiles and expected evidence are designed at the validation design gate. **Nothing has been run,
and no implementation-specific test suite exists.**

## Assurance model (lean, risk-based — the product owner, 2026-09-20)

**Test to prove the architecture, not to prove the test harness.**

- Every activity below maps to an acceptance criterion, an architectural invariant, a material failure mode, a
  regression risk, or release integrity — and says so.
- Each carries three lines: **why this test exists**, **what architectural claim it proves**, **what would fail if we
  omitted it**. Anything that could not answer all three has been removed, and the removals are recorded in §6.
- Shape: one normal-path proof · one meaningful overload or failure proof per major architectural claim · cleanup and
  leak verification wherever cloud resources exist · targeted reruns after defects · one designated final regression
  pass.
- **Stop-testing rule:** when the acceptance criteria and invariants have evidence, the designated failure experiments
  pass, the final regression passes, cleanup is proved and no blocker remains — stop. Further testing needs a new
  defect, a change, a new material risk, or the product owner's instruction.
- **Smallest justified rerun:** after a correction, rerun only what proves the correction, unless the changed component
  invalidates broader evidence — and then say which evidence.
- **A test is evidence only if it can fail.** Every invariant gets a deliberate failure experiment in a throwaway
  deployment, with the normal system passing before and after.

**Measurement honesty.** A capacity claim is only as good as its method: the load profile, the measurement point and the
percentile are recorded with every result (OPS-004). Numbers come from measurement at the educational scale (CON-007),
never from this plan.

## Proposed validation themes

| Theme | What must be shown | Requirements | Why this test exists · What it proves · What would fail without it |
|---|---|---|---|
| **VT-1 Promise at stated capacity** (normal path) | At the assumed daily peak, admitted requests meet the stated promise at the stated percentile, measured by the recorded method | BUS-003, LOD-003, NFR-001, OPS-004 | *Why:* acceptance criterion — the headline promise. *Proves:* the stated capacity is real, not aspirational. *Without it:* every later overload result is unanchored, because "normal" was never established |
| **VT-2 Overload behaviour is the stated rule** | Beyond capacity the system does what it said: admits, sheds or degrades by the stated rule; refusals are explicit, fast and typed; no unbounded wait; fairness holds across depots | BUS-001, FUN-001, LOD-002, LOD-004, LOD-005, LOD-008, LOD-009, NFR-002, NFR-004 | *Why:* the central architectural claim. *Proves:* overload behaviour is designed, not emergent. *Without it:* the design is a promise with no evidence, exactly the state the incident exposed |
| **VT-3 Retries cannot amplify** | Under the burst, bounded retries plus honoured retry guidance keep offered load bounded; repeated submissions are safe and non-duplicating | FUN-002, FUN-004, LOD-007 | *Why:* material failure mode (RSK-01) — the incident's turning point. *Proves:* the retry contract holds under stress. *Without it:* a correct system can still collapse from client behaviour |
| **VT-4 Downstream limits respected** | The architecture stays inside model-service and records-system quotas; refusals are recognised as saturation, not failure; unconfirmed currency withholds rather than serves | LOD-001, LOD-006, LOD-010, FRS-C-003, CMP-001 | *Why:* invariant plus inherited risk (Episode 01 RR-13). *Proves:* our capacity ends where the platform's does, and the safe behaviour is preserved there. *Without it:* the system's worst moment is also its least tested |
| **VT-5 Freshness and answering coexist** | Under a bulletin burst, both workloads keep their floors; when change processing is slowed, the Episode 03 watermark stalls visibly, lag is reported and the breach alerts | BUS-002, FRS-C-001, FRS-C-002 | *Why:* acceptance criterion and the Episode 03 interaction. *Proves:* the trade-off is chosen and visible, not silent. *Without it:* Episode 03's currency claim could lapse unnoticed under load |
| **VT-6 Invariants hold under pressure** (regression) | The Episode 02 eligibility suite and the Episode 03 currency behaviour pass during shedding, degradation and recovery; no cache or queue crosses a user or a currency basis; refusals leak nothing | LOD-001, LOD-009, SEC-001, SEC-002, DATA-001, CMP-001 | *Why:* regression risk created by every capacity mechanism. *Proves:* performance work did not buy correctness shortcuts. *Without it:* the most likely regression in this episode goes undetected |
| **VT-7 Saturation is observable** | Capacity, headroom, queue age, shed rate, degradation state and downstream throttling are visible in near real time; the four distinct alerts fire for their own causes | BUS-004, LOD-010, OPS-001, OPS-002 | *Why:* acceptance criterion (OBJ-6). *Proves:* the system can be operated and its capacity claimed before an incident. *Without it:* operators learn about saturation from users |
| **VT-8 Bounded recovery** | After demand falls, normal service resumes within the bounded time without manual intervention; the backlog and the retry herd do not re-create the spike | NFR-003, LOD-005, OPS-002 | *Why:* material failure mode (RSK-07). *Proves:* recovery is part of the design. *Without it:* the outage can outlast its cause and no one would know until it happened |

## Ruled behaviours the validation must demonstrate

Refined at E2 (2026-09-20) from the PD-E04 rulings and the proposed ADRs. **No new themes were added**: the existing
eight now carry more precise assertions.

| Ruling / decision | What validation must show | Theme |
|---|---|---|
| **Eligibility is per request** (Episode 02) | No capacity mechanism — buffer, coalescing, cache, degradation step — reuses another user's decision or result | VT-6 |
| **Known stale is not current; withhold rather than serve** (Episode 03) | Saturation that prevents a currency check produces a withheld answer, counted as a **capacity** outcome, never a served one | VT-4, VT-5 |
| **Degrade capability, not trust** | Every rung of the degradation ladder runs with the trust path intact; the response states what was reduced; retrieval-only never occurs | VT-2, VT-6 |
| **Caller-visible overload contract** | Every non-served request produces an explicit typed outcome within the refusal deadline — never a silent timeout — and the four outcomes are distinguishable | VT-2 |
| **Capacity is a stated, measured number** (ADR-001) | The promise holds at the stated concurrency, measured by the recorded method; the method is reproducible | VT-1 |
| **Bounded excess: admit, hold briefly by age, or refuse** (ADR-002) | Work that can no longer meet its deadline is discarded **before execution** and its caller told; the buffer never grows without bound | VT-2, VT-8 |
| **Floors for both workloads** | Under a bulletin burst both floors hold; neither workload reaches zero; fair share prevents one depot consuming the answering pool | VT-5, VT-2 |
| **Freshness degrades visibly** (ADR-003) | When change processing is held to its floor, the watermark stalls, lag is reported and a distinct alert fires | VT-5, VT-7 |
| **Downstream is never oversubscribed** (ADR-005) | Permits bound our demand; rejections are classified as saturation, not failure; adaptive reduction engages and restores | VT-4 |
| **Retries bounded by the architecture** (ADR-006) | Guidance is jittered, the budget is enforced server-side, repetition is safe and non-duplicating, identical in-flight questions coalesce per user | VT-3 |
| **Saturation is seen before users feel it** (ADR-007) | Queue age leads; the four alerts fire for their own causes and are not merged | VT-7 |
| **Bounded, automatic recovery** (ADR-008) | Staged ramp with hysteresis; no synchronised herd; freshness catch-up does not starve answering; "recovered" means the promise holds again | VT-8 |

## Candidate failure experiments

Deliberate faults, each in a separate throwaway deployment, with the normal system passing before and after. The exact
faults are designed with the architecture; nothing is implemented yet. **Three headline experiments are proposed**, following the Season 1 pattern of a teaching progression.

| Candidate | What would be broken | What must then fail |
|---|---|---|
| **FX-1** Unbounded queueing | Admission control removed; every request queued | VT-2: latency collapses past the promise while the system still reports "success"; the queue converts overload into a useless wait (RSK-03) |
| **FX-2** Unbounded retries (intellectual peak) | Retry budget, backoff and jitter removed; retry guidance ignored | VT-3: offered load multiplies, and a survivable burst becomes an outage — the system defeats itself with well-intentioned clients (RSK-01) |
| **FX-3** Degradation that bypasses a required trust check | A degradation rung that serves a cached or unverified result to relieve load (ADR-004, TT-01) | VT-6: the Episode 02/03 invariants break — proving the trust path must be structural, not documented (RSK-02) |
| FX-4 (candidate, not headline) | Change processing given unlimited priority during a burst | VT-5: answering is starved, or freshness stalls silently — demonstrating why both need floors (RSK-04) |

## Scope discipline for the later gates

Explicitly **not** planned, to keep assurance proportionate:

- no test-of-test machinery, unless a demonstrated harness defect creates a material evidence risk;
- no repeat of Episode 02 and Episode 03 suites beyond the designated regression (VT-6) and the final pass;
- no full-suite reruns after documentation, manifest, report or unrelated tooling changes;
- no large-scale or realistic-volume load testing: overload is demonstrated at small scale with deliberately small
  limits (CON-007);
- no per-mechanism micro-benchmarks; measurement exists to support the promise (VT-1), not to profile components;
- no second capacity measurement unless an input to the capacity model changed;
- no separate test per ADR: the ADRs are proved through the eight themes above;
- no controller-tuning study: the adaptive reducer (ADR-005) is proved by VT-4's behaviour at the boundary, not by
  characterising its response curve.

**Approximate size at the validation design gate (unchanged by E2):** 8 themes, 3 headline failure experiments, 1
cleanup and resource-leak verification, and 1 designated final regression pass — roughly 12–15 designed activities in
total, not a suite per requirement. **E2 added architectural detail without adding activities**, which is the lean model
working as intended. Requirements that a theme cannot reasonably prove are marked `review` in the requirement set and
are checked by inspection instead.

## Traceability

**Chain** (unchanged Season 1 model): requirement → decision → control → test → observed result → evidence.

**At this gate:**
- every requirement names a validation theme or `review`;
- decisions, controls and test IDs are added at the later gates;
- no traceability matrix is generated here, and the updater is not run.
