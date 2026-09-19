# ADR-002 — Convergence-aware serving and per-class pending behaviour

**Status:** accepted (2026-09-16) · **Answers:** DQ-C · **Options:** Option 3 with Option 2 applied narrowly

## Context
FRS-002 is an externally observable safety property, not an index-latency requirement (2026-09-16). The request
path must therefore be able to *not trust* derived state. Episode 02 already reads the authoritative classification
record per retrieved chunk, so a channel to authority exists at answer time. Over-blocking is a real cost (incident 4),
so "withhold everything whenever anything might be stale" is not acceptable either.

## Decision
**Known stale is not current.** A warning banner is not a safety control: the architecture does not present a known-old
revision as an answer merely because a notice accompanies it.

**Every candidate is in exactly one state**, and staleness is never represented only as an age number:

| State | Meaning | Served? |
|---|---|---|
| **Known current** | The authoritative record confirms this version is the effective one, and derived content matches it | Yes |
| **Known pending** | A change is known to be effective in the record and derived state has not caught up | No — not as current |
| **Known superseded, withdrawn or deleted** | Authority says this content is no longer in force | No |
| **Unknown** | The system cannot establish the state — no confirmation, or outside what convergence can vouch for | No — treated conservatively |

(The domain model may rename these; what matters is that all four are distinguishable.)

The request path serves derived content only where its currency can be established, using three inputs:

1. **Authoritative status confirmation** — the existing per-chunk verification read is extended to return status,
   effective version and supersession (ADR-001). Superseded, withdrawn, deleted or version-mismatched candidates are
   discarded before generation.
2. **Pending set** — documents known to have changed but not yet applied are marked; their content is not served as
   current.
3. **Watermark** — the proven-complete point (ADR-003). If the watermark is older than its target, the system enters
   conservative mode for safety-critical classes.

**Behaviour while a change is pending, by class:**

| Change class | Behaviour | Basis |
|---|---|---|
| Supersede, withdraw | Old content is not answered as current from the next request | Locked by decision |
| Upward reclassification | Enforced from the next request | Episode 02, inherited |
| Deletion | Not retrievable, not presented as current, from the next request | Locked by decision |
| **New version — all documents (default)** | **Withhold.** Once authority says a newer version is effective, the previous version is not presented as current; the affected answer waits until the effective version is retrievable | **Decided (2026-09-16)** |
| **New version — a future class with different approved behaviour** | The architecture keeps a **policy hook** so a document class may later be given different behaviour, but only through a separate, explicit business and safety policy decision. No such class exists in Episode 03 | Ruled |
| Downward reclassification | Content becomes available only once the change is effective in the record, and within its window | SEC-002 |

## Alternatives considered
| Alternative | Why not |
|---|---|
| Withhold on every pending change | Safe and simple, but turns every routine revision into unavailability (incident 4 generalised); over-blocking is a real cost |
| Serve stale content silently until re-indexed | Reproduces incident 1 |
| Trust the pending set alone, without authority confirmation | A missed notification would leave the old state trusted until reconciliation; the safety class cannot wait for a cadence |
| Trust authority confirmation alone, without a pending set | Works for safety, but leaves the system unable to say what it does not know, and gives no system-wide evidence |

## Consequences
- **Good:** FRS-002 holds independently of index latency; unavailability is bounded and explained; each answer can state
  the version confirmed at answer time.
- **Cost:** a slightly larger authority read per candidate; a pending-state lookup per request; and unavailability while
  a newer effective version is not yet retrievable — accepted deliberately, because presenting a
  known-old revision would turn a warning into a safety control. The pending window is bounded and measured (NFR-003).
- **Fail-closed :** if the authority read or the pending state is unavailable, safety-critical content
  is withheld. Other content may continue **only** where the authoritative request-time check can still establish that the
  candidate is current and eligible. An outage of the convergence system is never a reason to ignore it: the outage stays
  observable and the system's freshness claim weakens accordingly — it may keep answering some requests while being unable
  to claim full convergence.
