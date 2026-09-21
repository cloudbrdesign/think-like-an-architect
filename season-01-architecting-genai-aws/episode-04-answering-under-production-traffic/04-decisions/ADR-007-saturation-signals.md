# ADR-007 — Saturation is detected by queue age, and its causes are distinguished

**Status:** **ACCEPTED in direction** (2026-09-20).

**the product owner (2026-09-20):** ACCEPTED. Queue age may lead where queueing exists, but E3 preserves multiple signals; queue depth alone is never treated as saturation.

## Context
During the incident, operators learned about saturation from users. Utilisation looked "high" for half an hour, which
says nothing, and the model-service rejections looked like errors rather than a quota boundary (RSK-05). LOD-010 and
OPS-001/002 require that saturation is visible and that different causes are distinguishable.

## Decision question
DQ-G: which signals define saturation, and how are "too busy", "broken" and "not current" told apart?

## Options considered
1. Utilisation thresholds (busy-ness of the workers).
2. **Queue age (and admission-wait) as the lead signal, with rejection, latency-tail and freshness-lag signals beside
   it.**
3. Error-budget burn as the only operational signal.
4. Synthetic probes alone.

## Proposed decision
Option 2.
- **Lead signal:** the age of the oldest admitted-but-unstarted work — the quantity that predicts a broken promise
  before it breaks (TP-10).
- **Supporting signals:** admitted concurrency versus permits; shed rate by reason; downstream rejection rate per
  dependency; tail latency of admitted work; freshness lag and watermark age (Episode 03); retry-budget exhaustion.
- **Four distinct alerts, never merged:** sustained answering saturation · downstream quota exhaustion · stalled
  freshness watermark · failed or stalled recovery.
- **Distinct outcome accounting:** refused-for-capacity, withheld-for-currency and failed are counted separately, so the
  incident's "can't answer" spike is visibly a capacity event, not a content event (FRS-C-003).
- Synthetic probes run at a fixed cadence to give a signal that exists even when real traffic has stopped arriving.

## Why
- Utilisation is ambiguous: a system at 90% with a stable queue is fine, and one at 60% with a growing queue is not.
- Queue age maps directly onto the promise, so the alert threshold is derived from the contract rather than invented.
- Separating causes is what turns an alert into an action; merging them is why the incident took half an hour to read.

## Trade-offs
- Age requires clocks and per-item timestamps.
- More signals means more dashboards to maintain (CON-004); the mitigation is that the four alerts are few and named.
- Probes add a small constant load.

## Rejected alternatives
- **Utilisation thresholds:** ambiguous, and the reason operators could not see the incident.
- **Error budget only:** a good long-horizon signal, too slow for a four-minute burst.
- **Probes only:** measures the probe path, not the users' experience.

## Consequences
- Every queued or admitted item carries a timestamp and a deadline.
- Capacity claims become reviewable after each incident (CMP-002), because the signals and method are recorded.
- The lab can expose all four alerts at tiny scale.

## Validation required
VT-7 (signals present and alerts distinct), VT-5 (stalled watermark surfaces separately), VT-2 (shed reasons counted).

## What would cause us to revisit
- Measurement shows admission wait is near zero because the buffer is rarely used, making downstream rejection the
  better lead signal.
- The platform provides a trustworthy saturation signal of its own that is cheaper to consume.
