# ADR-002 — Admission control at the edge, with a narrow age-bounded buffer

**Status:** **ACCEPTED in direction** (2026-09-20).

**the product owner (2026-09-20):** ACCEPTED. The buffer absorbs a short, known burst only. It must never become the default place where overload is hidden. Its capacity and maximum age are explicit, and expired work leaves through an explicit outcome rather than silently waiting.

## Context
Excess demand must go somewhere. The incident put it in an implicit, unbounded queue made of client connections and
retries, which converted overload into a 40-second wait and then into refusals anyway. LOD-004 requires a stated rule;
LOD-005 requires that work which can no longer meet the promise is discarded before it is executed.

## Decision question
DQ-C: queue, shed, or both — and what bounds the queue?

## Options considered
1. Pure immediate shedding (analysis Option 1).
2. Bounded-age queue in front of the workers (analysis Option 2).
3. **Admission control as the default, plus a narrow buffer bounded by age, used only for short predictable bursts.**
4. Unbounded queueing (the implicit status quo).

## Proposed decision
Option 3.
- Admission is decided **at the edge**, before any expensive work, against the partition's permit budget (ADR-003).
- A buffer exists only where the burst is short and predictable (shift start). It is bounded by **age**, expressed as a
  fraction of the promise budget — not by length.
- Work whose remaining budget cannot cover a normal answer is **discarded before execution**, and its caller is told
  (LOD-002).
- When the buffer is full, behaviour degrades to immediate refusal.

## Why
- Admission control is the only mechanism that protects the system before work is spent.
- An age bound is the property users actually care about; a length bound says nothing about waiting time (TP-10).
- Discarding before execution is what stops the system spending its scarcest resource on abandoned requests.

## Trade-offs
- A buffer adds a second place where policy lives, and it briefly stores user questions (DATA-002, ASM-010).
- Age bounds need a clock and a budget model; that is real complexity.
- Some users wait a little rather than being refused immediately — acceptable at seconds, not at tens of seconds.

## Rejected alternatives
- **Pure shedding:** refuses a burst that would have fitted; wastes a genuine opportunity at shift start.
- **Queue as the main mechanism:** relocates overload rather than answering it; FX-1 exists to demonstrate this.
- **Unbounded queueing:** the failure being corrected.

## Consequences
- Queue age becomes the lead saturation signal (ADR-007).
- The buffer's retention and content limits are a data obligation, not an implementation detail.
- Recovery must handle a backlog that may contain expired work (ADR-008).

## Validation required
VT-2 (the stated rule, including pre-execution expiry and explicit refusal), VT-8 (backlog at recovery). FX-1 removes
admission control and must produce latency collapse with apparent success.

## What would cause us to revisit
- Measurement shows the shift-start burst is longer than the buffer can honestly absorb.
- Retention policy forbids storing questions even briefly.
- Evidence that refusal at the peak is more acceptable to users than a short wait.
