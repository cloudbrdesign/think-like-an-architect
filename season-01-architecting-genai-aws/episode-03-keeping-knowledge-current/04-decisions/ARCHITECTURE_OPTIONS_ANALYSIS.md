# Architecture Options Analysis — Kestrelmoor Knowledge Assistant: keeping the knowledge base current

**Status:** accepted with refinements (2026-09-16). Options and trade-offs only; no service selection, no
deployment. **All five options stay in the record:** the rejected ones are part of the architectural reasoning and are not
removed because a recommendation exists.

**Baseline that must survive every option (Episode 02, CON-002):** identity from a verified token; entitlements from the
authoritative sources per request; an eligibility decision outside the model; one mandatory constraint per tier
evaluated inside the search; per-chunk verification against the current classification record before generation; fail
closed; content-free audit.

**The question these options answer:** how does a derived retrieval system stay faithful to an authoritative records
system as that authority changes — and how does it prove what it knew, when it knew it, and how it behaved while
convergence was incomplete?

**Structural observation that shapes the field.** The Episode 02 request path *already* reads the authoritative
classification record for every retrieved chunk. So the architecture already has a channel to authority at answer time.
The options differ mainly in two properties:
1. **what the request path asks authority for**, and therefore what it is willing to trust in the index; and
2. **how the change path establishes completeness** — that nothing has been missed.

---

## Option 1 — Faster change pipeline (converge by speed)

**Architectural thesis:** staleness is a latency problem. Process changes as they arrive, quickly, with retries and
alerting; the index is trusted, and freshness is a service-level target.

| Aspect | Behaviour |
|---|---|
| Request path while derived state is stale | Unchanged from Episode 02. The index is trusted; verification compares label, scope and version only |
| Change-path model | Notification-driven incremental apply, with retries and a dead-letter path |
| Lost changes | Only failures the pipeline itself observes. A notification that never arrives is invisible |
| Ordering / idempotency | Can be added per document (apply if the version is newer), but correctness is unprovable while completeness is unknown |
| Version replacement | In-place update of a document's chunks |
| Deletion | Delete chunks on the deletion event; other derived copies handled case by case |
| Freshness / convergence evidence | Pipeline latency and queue depth — processing latency, not provable freshness |
| Failure behaviour | Silent loss (incident 2); stale content keeps being served with no signal |
| Operational model | Simplest to build and run; one pipeline, one dashboard |
| Scaling | Comfortable at ~3,000 changes/day; bursts queue and lag |
| Security implications | No new eligibility risk if writes are ordered, but repairs are ad hoc and unaudited |
| Preserves Episode 02 | Yes |
| FRS-002 | **No.** Supersession by another document keeps a valid record with an unchanged label, scope and version; it is answered as current until re-indexed — incident 1 |
| FRS-004 | **No.** Delivery without loss detection |
| FRS-005 | Partly, per document |
| SEC-001 | Yes |
| Trade-offs | Cheapest and simplest; teaches nothing about completeness, and fails two invariants |
| Risks | RSK-01, RSK-02, RSK-09 |
| What would make us reject it | It is already rejected: it is what Kestrelmoor has, made faster, and the incidents were not latency failures |

---

## Option 2 — Authority-checked request path (validity at answer time)

**Architectural thesis:** the index is a *candidate generator*, never a source of truth about status. Before any
candidate is used, the request path asks authority what that document currently is.

| Aspect | Behaviour |
|---|---|
| Request path while derived state is stale | Episode 02's pre-generation verification is extended: for every candidate, read the authoritative record's status, effective version and supersession. Superseded, withdrawn, deleted or version-mismatched candidates are discarded. Safety is independent of index lag |
| Change-path model | Incremental ingestion, needed only for *availability* (new content becoming answerable) |
| Lost changes | Not a safety problem; still an availability problem, and still invisible without reconciliation |
| Ordering / idempotency | Matters for index sanity, not for safety |
| Version replacement | Old chunks fail the live check the moment the record changes; new chunks appear when indexed |
| Deletion | Unretrievable immediately (the record is gone or marked deleted); physical removal still required for obligations |
| Freshness / convergence evidence | The strongest per-answer evidence: every answer names the record version confirmed at answer time. Index lag remains an availability metric |
| Failure behaviour | Authority unavailable → fail closed (already the Episode 02 behaviour). Availability is coupled to the records system |
| Operational model | Simple change pipeline; the burden moves to per-request authority reads |
| Scaling | Cost scales with candidates per question, not corpus size; question bursts hit the records system. Any cache of status reintroduces staleness unless it is bounded and fails closed |
| Security implications | Strong: pipeline defects cannot produce unsafe answers. The status read must be authenticated and content-free |
| Preserves Episode 02 | Yes — it extends the existing verification step rather than adding a path |
| FRS-002 | **Yes**, from the next request |
| FRS-004 | Partly — loss is still undetected |
| FRS-005 | Partly |
| SEC-001 | Yes |
| Trade-offs | Buys safety with per-request authority reads; leaves completeness unsolved |
| Risks | Records-system availability and latency; cache temptation |
| What would make us reject it | If per-candidate authority reads cannot meet answer latency, or the records system cannot serve that read rate |

---

## Option 3 — Convergence-aware serving: pending set and watermark (know what you do not know)

**Architectural thesis:** the system serves derived state only where it can show that derived state is current. It keeps
two small pieces of state: a **pending set** (documents known to have changed but not yet applied) and a **watermark**
(the point up to which completeness has been *proven*, advanced only by reconciliation — never by the notification
stream). Anything pending, or outside the proven watermark, is not trusted.

| Aspect | Behaviour |
|---|---|
| Request path while derived state is stale | Candidates whose document is in the pending set, or whose state cannot be vouched for by the watermark, are not trusted: suppressed for safety-critical classes, and reported as pending rather than answered as current. Watermark older than its target → conservative mode |
| Change-path model | A notification writes a pending-set entry immediately (a cheap metadata write) and queues the content work; applying the change clears the entry |
| Lost changes | Reconciliation against the full authoritative export discovers changes never notified, repairs drift and is the only thing that advances the watermark |
| Ordering / idempotency | Apply by authoritative version and effective time; monotonic — an older version can never overwrite a newer one; duplicates are no-ops |
| Version replacement | Per-document generation: the new generation is written completely, then switched; the old is removed afterwards; the pending entry clears at the switch |
| Deletion | The pending set makes a deleted document unretrievable at once; propagation then removes it across the derived-copy surface, with a content-free deletion ledger |
| Freshness / convergence evidence | "All changes effective before T are applied; N documents pending; oldest pending age A; reconciliation last completed at R" — plus canary changes to show the measurement is not vacuous |
| Failure behaviour | Pending set unavailable → fail closed for safety classes. Reconciliation overdue → the watermark stalls → conservative mode. Partial ingestion leaves a pending entry, never a half-trusted document |
| Operational model | More machinery than Options 1–2: pending set, watermark, reconciliation, repair. In exchange, failures are visible by construction |
| Scaling | Per request: one small lookup keyed by the candidate documents. Reconciliation grows with the corpus and can be partitioned and scheduled |
| Security implications | Conservative by default: unknown means untrusted, so pipeline defects cannot widen eligibility |
| Preserves Episode 02 | Yes; the eligibility decision and constraint are untouched |
| FRS-002 | **Yes**, once the notification lands — and, for a missed notification, at reconciliation. The residual gap between "effective" and "discovered" is the reason for the narrow Option 2 check in the recommendation |
| FRS-004 | **Yes** — reconciliation is the completeness proof |
| FRS-005 | **Yes** — authoritative version ordering |
| SEC-001 | **Yes** |
| Trade-offs | The most machinery to build and explain; the payoff is provable convergence and bounded behaviour |
| Risks | Pending-set completeness depends on notifications plus reconciliation cadence; watermark semantics must be understood by operators |
| What would make us reject it | If the pending set cannot be kept complete and cheap, or if operators cannot reason about the watermark |

---

## Option 4 — Snapshot rebuild and switch (immutable generations)

**Architectural thesis:** never mutate the index. Build a complete generation from an authoritative export, verify it
against that export, and switch atomically. Completeness and provenance hold by construction.

| Aspect | Behaviour |
|---|---|
| Request path while derived state is stale | Serves a generation stamped with its export time. Anything changed since that export is unknown unless an invalidation mechanism is added |
| Change-path model | Export → build → verify → switch, on a cycle |
| Lost changes | Structurally impossible within a generation: the generation *is* the export |
| Ordering / idempotency | No incremental mutation, so no ordering problem at all |
| Version replacement | Implicit in the next generation |
| Deletion | Deleted documents are simply absent from the next generation; obligation windows depend on the cycle, and superseded generations must themselves be destroyed |
| Freshness / convergence evidence | Excellent and simple — "this index is export T" — at the granularity of the rebuild cycle |
| Failure behaviour | A failed build keeps the previous generation: safe for eligibility, stale for freshness |
| Operational model | The simplest mental model; heavy compute; storage for two generations |
| Scaling | Rebuilding ~180,000 documents takes days (ASM-008), and re-embedding carries the cost CON-007 warns about |
| Security implications | Change effects are isolated; the switch must be atomic per tier so labels and content never mix across generations |
| Preserves Episode 02 | Yes |
| FRS-002 | **No** at any realistic cycle: supersession would wait for the next generation |
| FRS-004 | Yes | 
| FRS-005 | Yes (not applicable) |
| SEC-001 | Yes |
| Trade-offs | Buys completeness and provenance with latency and cost |
| Risks | Rebuild becomes the routine fix (RSK-10); cost pressure against Episode 05 |
| What would make us reject it as the primary mechanism | It cannot meet the next-request or 4-hour windows; it is, however, the right shape for repair and rebuild (DQ-H) and for reconciliation's reference data |

---

## Option 5 — Do not derive the critical class (authority-side answering)

**Architectural thesis:** the cheapest derived state to keep faithful is the derived state you never create. Answer
safety-critical procedures from the authority at request time; index everything else.

| Aspect | Behaviour |
|---|---|
| Request path while derived state is stale | For the safety class there is no derived state: the current document is resolved from the authority and used directly. Other classes use the index |
| Change-path model | Nothing to propagate for the safety class; Option 1 or 3 for the rest |
| Lost changes | Irrelevant for the class; unchanged for the rest |
| Ordering / idempotency | Not applicable for the class |
| Version replacement | Not applicable for the class |
| Deletion | Immediate for the class |
| Freshness / convergence evidence | Perfect for the class ("we read the record"); unchanged for the rest |
| Failure behaviour | An authority outage removes the most important capability entirely |
| Operational model | Two answering paths to build, operate, secure and test |
| Scaling | Authority read load per question in the class; retrieval quality drops without an index — the semantic search across sections that made the assistant useful in Episode 02 |
| Security implications | **A second retrieval path is a second place eligibility must be enforced.** Episode 02's "no route reaches content without the eligibility decision" must hold on both paths |
| Preserves Episode 02 | Only with care; it adds the kind of second path Episode 02 deliberately refused |
| FRS-002 | Yes for the class; unchanged elsewhere |
| FRS-004 | Unchanged elsewhere |
| FRS-005 | Not applicable |
| SEC-001 | At risk — the new path must re-implement enforcement |
| Trade-offs | Removes a whole class of staleness; costs retrieval quality and adds an enforcement surface |
| Risks | Two-path divergence; weaker answers for exactly the questions that matter most |
| What would make us reject it as the architecture | The retrieval-quality loss and the second enforcement path. Its *principle* is worth keeping: never derive what you can read cheaply — which is why **status**, not content, is read from authority |

---

## Decision criteria

| ID | Criterion | Type |
|---|---|---|
| C1 | FRS-002 holds without depending on index latency | Blocking |
| C2 | Completeness is provable (FRS-004): delivery **and** loss detection | Blocking |
| C3 | Ordering safety (FRS-005) under duplicates and replay | Blocking |
| C4 | Episode 02 eligibility preserved at all times (SEC-001) | Blocking |
| C5 | Over-blocking is bounded and measured (NFR-003, incident 4) | Weighted |
| C6 | Freshness evidence quality (FRS-008, OPS-003) | Weighted |
| C7 | Operable by six engineers (CON-003) | Weighted |
| C8 | Cost and scale at assumed volume and bursts (NFR-001, CON-007) | Weighted |
| C9 | Testable, including FX-1…FX-3 | Weighted |

## Comparison

| Criterion | 1 Faster pipeline | 2 Authority-checked path | 3 Pending set + watermark | 4 Snapshot rebuild | 5 Non-derived class |
|---|---|---|---|---|---|
| C1 FRS-002 | ✗ | ✓ | ✓ (with reconciliation cadence) | ✗ | ✓ for the class only |
| C2 FRS-004 | ✗ | ✗ | ✓ | ✓ | ✗ elsewhere |
| C3 FRS-005 | ~ | ~ | ✓ | ✓ (n/a) | n/a |
| C4 SEC-001 | ✓ | ✓ | ✓ | ✓ | ✗ risk (second path) |
| C5 Over-blocking | ~ | ✓ | ✓ | ✗ (cycle-bound) | ✓ for the class |
| C6 Evidence | ✗ | ✓ per answer | ✓ per answer and system-wide | ✓ per generation | ~ |
| C7 Operability | ✓✓ | ✓ | ~ (most machinery) | ✓ (heavy but simple) | ✗ two paths |
| C8 Cost and scale | ✓✓ | ~ (per-request reads) | ✓ | ✗ (days per rebuild) | ~ |
| C9 Testability | ~ | ✓ | ✓✓ (FX-1…3 map directly) | ~ | ~ |

## Recommendation — accepted (2026-09-16)

**Approved formulation:**

> **Convergence-aware derived retrieval + authoritative request-time status confirmation + generation-based repair and
> rebuild.**

**Three responsibilities, deliberately not collapsed into one mechanism:**

| Responsibility | Mechanism |
|---|---|
| **Protect the request** | Authoritative request-time status confirmation (Option 2's principle, extending the Episode 02 record read) |
| **Prove convergence** | Pending state plus a reconciliation-advanced watermark (Option 3, the spine) |
| **Rebuild when necessary** | Build a complete generation, verify it, then switch (Option 4, exceptional) |

**Trust boundary (locked):** the records system is authoritative; the retrieval index is derived state; the pending and
convergence state is *also* derived operational state. Neither becomes a second source of truth. On disagreement,
authority wins; where authoritative state cannot be established, the approved fail-closed behaviour applies.

**In detail — Option 3 as the spine, with Option 2 applied narrowly:**
1. **Never derive authority.** Status, effective version and supersession are read from the authoritative record, by
   extending the per-chunk verification read Episode 02 already performs (Option 5's principle, applied to status rather
   than content; decided: extend the existing read, add no second source of truth, and invent no field merely to
   simplify implementation).
2. **Know the boundary of trust.** A pending set and a reconciliation-advanced watermark say what the system does not
   know; anything unknown is not served as current (Option 3).
3. **Prove completeness by reconciliation, never by delivery.** Notifications make the system fast; reconciliation makes
   it correct (Option 4's export, used as reference data rather than as the serving mechanism).
4. **Repair and rebuild** use generation-and-switch, as the exceptional path (Option 4).

**Why:** it is the only combination that satisfies all four blocking criteria while bounding over-blocking and producing
evidence at both levels — per answer ("this is the version confirmed at answer time") and system-wide ("every change
effective before T is applied or pending"). It also teaches the distinction the episode exists for: *delivery is not
completeness, and latency is not freshness.*

**Refinement (R-10):** when authority says a newer version is effective but that version is not
yet retrievable, the previous version is **withheld** — not served with a currency notice. Known stale is not current, and
a warning banner is not a safety control. A policy hook remains so a future document class may be given different
behaviour, subject to its own explicit business and safety decision.

**Refinements carried into the ADRs:**

| ID | Refinement |
|---|---|
| R-10 | Withhold a known-old version by default once a newer version is effective; policy hook retained |
| R-11 | Extend the existing authoritative record read; no second source of truth |
| R-12 | Watermark per change class with a global conservative floor, and its semantics made precise in ADR-007 |
| R-13 | Class-sensitive reconciliation as a policy shape; numeric cadence measured during implementation |
| R-14 | Convergence state unavailable: fail closed for safety-critical content; other content only where the request-time check still establishes currency; the outage stays observable |
| R-15 | Demonstrate generation-based rebuild and switch at educational scale |

**Rejected as the architecture:** Option 1 (fails C1 and C2 — it is today's system, faster), Option 4 (fails C1 at any
realistic cycle; retained for repair and rebuild), Option 5 (fails C4 by adding a second enforcement path, and costs the
retrieval quality that makes the assistant useful; its principle is retained for status).

## Proposed ADR set

| ADR | Subject |
|---|---|
| ADR-001 | Authoritative state model for change |
| ADR-002 | Convergence-aware serving and per-class pending behaviour |
| ADR-003 | Change detection and completeness (notifications + reconciliation) |
| ADR-004 | Ordering and idempotency |
| ADR-005 | Version replacement by generation and switch |
| ADR-006 | Deletion as a derived-state obligation, with evidence |
| ADR-007 | Freshness measurement and evidence |
| ADR-008 | Repair and rebuild |

No option is implemented, and no service is chosen. Service selection belongs to the implementation design gate.
