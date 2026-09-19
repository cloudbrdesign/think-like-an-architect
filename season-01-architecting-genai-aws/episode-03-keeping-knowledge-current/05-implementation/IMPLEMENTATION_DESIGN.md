# Educational Implementation Design — Kestrelmoor Knowledge Assistant: keeping the knowledge base current

**Stage:** implementation design · **Status:** as built (2026-09-16) · **Date:** 2026-09-16

**What this is:** the design of the free educational implementation of the approved Episode 03 architecture
(ADR-001 … ADR-008), built on the Episode 02 implementation, which stays intact.

**Approved architecture, unchanged:**

> **Convergence-aware derived retrieval + authoritative request-time status confirmation + generation-based repair and
> rebuild** — protect the request · prove convergence · rebuild when necessary.

**Trust boundary, unchanged:** the records system is authoritative; the retrieval index is derived; the convergence
state is *also* derived operational state. Authority wins on disagreement. Fail closed when authoritative state cannot
be established.

**Rule of the design (Episode 02's, unchanged):**
- **Local:** every rule that can be shown without a cloud runs locally, with unit tests and no credentials.
- **AWS:** claims about managed retrieval, permissions and service behaviour are verified against AWS, never simulated
  and then reported as verified.

---

## 1. What the learner builds

Episode 02's assistant, plus the change path that keeps its index faithful to the records system:

1. **Local core (no AWS, no cost)** — plain Python with unit tests:
   - the authoritative record state model (status, effective version, supersession) — `core/record_state.py`;
   - the four convergence states and the pending set — `core/convergence.py`;
   - monotonic, idempotent change application — `core/change_apply.py`;
   - per-document generations and the switch — `core/generations.py`;
   - the derived-copy graph and deletion obligations — `core/deletion.py`;
   - the watermark and freshness evidence — `core/freshness.py`;
   - Episode 02's eligibility, classification, constraint, verification, relevance and audit rules, unchanged.
2. **AWS deployment (billable, destroyed in the same session)** — the Episode 02 stack extended with the records
   authority, the change path, convergence state, reconciliation and rebuild.
3. **Validation harness** — the Episode 02 suite (regression) plus the Episode 03 themes VT-1 … VT-10 and the three
   headline failure experiments FX-1 … FX-3.

## 2. What changes from Episode 02, and what does not

| Episode 02 | Episode 03 |
|---|---|
| Classification record: label, scope, version | **Same record, plus authoritative lifecycle:** status, effective-from, supersession pointer (ADR-001) |
| Verification compares label, scope, version | **Plus status and effective version** — superseded, withdrawn, deleted or not-effective candidates are discarded (ADR-002) |
| Ingestion invoked by an operator for named documents | **Change path:** notifications create pending entries, then a change applier converges derived state (ADR-003) |
| No completeness mechanism | **Reconciliation** against the authoritative export, the only thing that advances the watermark (ADR-003) |
| Chunks replaced in place by re-ingesting | **Per-document generations** written complete, then switched (ADR-005) |
| Deletion = removing chunks | **Deletion across the actual derived-copy graph, with a content-free ledger** (ADR-006) |
| No freshness evidence | **Per-answer and system-wide freshness evidence** (ADR-007) |
| Re-index everything by hand | **Targeted repair, and verified generation rebuild** (ADR-008) |

**Unchanged and protected (SEC-001, CON-002):** identity from the verified token; per-request authoritative grants; the
eligibility decision outside the model; one mandatory constraint per tier evaluated inside the search; tier permissions;
fail-closed behaviour; the content-free audit record. The Episode 02 suite runs against Episode 03 as a regression
(VT-10).

## 3. Service selection

Every choice below is recorded the same way: responsibility · why it fits the ADR · alternative considered ·
failure mode introduced · operational cost · AWS-specific dependency. **The architecture is conceptually portable**: the
column "AWS-specific?" states whether any approved property depends on an AWS behaviour.

### 3.1 Authoritative records (the records system stand-in)

| | |
|---|---|
| **Responsibility** | Hold the authoritative record for every document: content version, **status**, **effective-from**, **supersession pointer**, classification label and scope, retention class (ADR-001) |
| **Choice** | **DynamoDB table** (extends Episode 02's classification table) + an S3 bucket for the synthetic source text |
| **Why it fits** | ADR-001 requires a consistent, per-request read of a small authoritative record; Episode 02 already reads this table on every request, and Episode 03 must **extend that read, not add a second source of truth** |
| **Alternative considered** | A separate "status service" (Lambda + its own store). Rejected: it would create a second authority to keep fresh — exactly what ADR-001 forbids |
| **Failure mode introduced** | The request path's dependency on one table deepens: a table outage fails closed (as Episode 02 already does) |
| **Operational cost** | On-demand reads per request; a few hundred items at educational scale |
| **AWS-specific?** | **No.** Any strongly-consistent key-value store with conditional writes satisfies ADR-001 and ADR-004 |

### 3.2 Change notification (low-latency signal)

| | |
|---|---|
| **Responsibility** | Carry "this record changed" quickly enough that a pending entry exists before content work finishes (ADR-003) |
| **Choice** | **DynamoDB Streams** on the records table → **Lambda (change notifier)** |
| **Why it fits** | The notification must come from the authority itself, not from the writer's goodwill: any write to the record — including one made by hand — produces a change signal. That makes FX-3's "drop notifications" a real fault to inject rather than a code path nobody uses |
| **Alternative considered** | **EventBridge + SQS** published by the writer: rejected because the writer could forget to publish, which confuses "the writer did not tell us" with "delivery lost it". **Polling only:** rejected — it cannot meet the next-request semantics for supersede/withdraw (ADR-002) |
| **Failure mode introduced** | Stream delivery is at-least-once and per-partition ordered; duplicates and retries are normal — handled by ADR-004's monotonic, idempotent application. Stream records expire (24 h), so a long outage genuinely loses changes: that is the honest condition reconciliation exists for |
| **Operational cost** | Stream reads and one short Lambda invocation per change |
| **AWS-specific?** | **No** for the architecture; the *fault injection* uses the stream's on/off switch, which any change feed has an equivalent of |

### 3.3 Change application (converging derived state)

| | |
|---|---|
| **Responsibility** | Apply a change to derived state: build the new generation, switch it, clear the pending entry (ADR-004, ADR-005) |
| **Choice** | **Lambda (change applier)**, invoked by the notifier and by reconciliation repairs |
| **Why it fits** | One component, one responsibility; the same path for notified changes, repairs and rebuild work, so ordering and idempotency are proved once (ADR-004) |
| **Alternative considered** | Step Functions: rejected for this episode — the orchestration would be more visible than the architecture, and the work per document is a few seconds. Recorded as the natural production evolution |
| **Failure mode introduced** | A failed invocation leaves a pending entry (never a half-trusted document) and is retried; a poison document would retry forever without the failure isolation in §4.5 |
| **Operational cost** | Sub-second to seconds per document at educational scale |
| **AWS-specific?** | **No** |

### 3.4 Convergence state (pending set and watermark)

| | |
|---|---|
| **Responsibility** | Record what is known-changed-but-not-applied, and what completeness has been proven (ADR-002, ADR-003, ADR-007) |
| **Choice** | **DynamoDB table** (`convergence`): one item per pending document, one item per change class watermark, one item per reconciliation run |
| **Why it fits** | The request path needs a cheap keyed lookup for the candidate documents; the watermark needs a conditional write so only a completed reconciliation advances it |
| **Alternative considered** | Keeping pending state in the records table: rejected — derived operational state must not live inside the authority (ADR-001), or the two become indistinguishable |
| **Failure mode introduced** | If this table is unavailable the system cannot prove convergence: fail-closed behaviour — safety-critical content withheld, other content only where the authoritative check still establishes currency, and the outage stays observable |
| **Operational cost** | One small read per request (batched across candidate documents) and a write per change |
| **AWS-specific?** | **No** |

### 3.5 Reconciliation (completeness)

| | |
|---|---|
| **Responsibility** | Compare the authoritative export with derived state, produce missing / extra / divergent, repair, and advance the watermark (ADR-003) |
| **Choice** | **Lambda (reconciler)**, started by the operator or a schedule; it reads the records table and the derived inventory |
| **Why it fits** | Reconciliation must read **authority**, never the notification stream; running it as its own component makes FX-3 (disable reconciliation) a single, honest switch |
| **Alternative considered** | Reconciling inside the applier: rejected — completeness would then depend on changes arriving, which is the fallacy the episode is about |
| **Failure mode introduced** | A reconciliation that cannot complete must **not** advance the watermark; overdue reconciliation stalls it and triggers conservative mode |
| **Operational cost** | One pass over the corpus per run; partitioned by change class at larger scale |
| **AWS-specific?** | **No** |

### 3.6 Retrieval, generation, identity, API (inherited)

| | |
|---|---|
| **Responsibility** | Unchanged Episode 02 responsibilities: two knowledge-base tiers on S3 Vectors, Titan embeddings, Nova Micro generation, Cognito identity, HTTP API with a JWT authorizer |
| **Why it fits** | CON-002 keeps the Episode 02 architecture as the baseline; reusing it exactly is what makes VT-10 a genuine regression |
| **Alternative considered** | None: changing them would reopen an approved architecture |
| **Failure mode introduced** | Unchanged |
| **Operational cost** | Unchanged (COST_AND_CLEANUP.md) |
| **AWS-specific?** | The *implementation* is; the architecture is not. The observed filter-size limits remain measured platform behaviour, not architectural constants |

## 4. How each approved decision becomes code

### 4.1 ADR-001 — authoritative state model
`core/record_state.py`: parses and validates the authoritative record's lifecycle fields; exposes
`status`, `effective_version`, `supersedes`/`superseded_by`, `effective_from`, and the rule **authority wins**. Content
never sets status (SEC-004): the parser reads only the record, never document text.

### 4.2 ADR-002 — convergence-aware serving
`core/convergence.py` defines the four candidate states — `KNOWN_CURRENT`, `KNOWN_PENDING`,
`KNOWN_SUPERSEDED_WITHDRAWN_DELETED`, `UNKNOWN` — and the serving rule: only `KNOWN_CURRENT` may be used.
`core/verification.py` gains the status and effective-version checks, so a superseded document fails **before**
generation even when its label, scope and version are unchanged. **Known stale is not current**: when a
newer version is effective but not yet retrievable, the answer is withheld; the policy hook exists and is not activated.

### 4.3 ADR-003 — change detection and completeness
`change/notifier.py` writes a pending entry per change; `change/reconciler.py` compares the authoritative export with
the derived inventory and advances the class watermark only on a completed pass. Notifications never advance it.

### 4.4 ADR-004 — ordering and idempotency
`core/change_apply.py`: a change applies only if its authoritative version is newer than the version reflected in
derived state; duplicates are no-ops; deletion is terminal for the record's lifetime; every rejection is recorded as
`SUPERSEDED_BY_NEWER` rather than silently dropped.

### 4.5 ADR-005 — version replacement
`core/generations.py`: a document's derived content is written as a complete generation keyed by the authoritative
version, verified, then switched by a single conditional write; the previous generation is retired afterwards. A failed
build leaves the previous generation serving and the document pending.

### 4.6 ADR-006 — deletion
`core/deletion.py`: the derived-copy graph is **discovered from this implementation** (section objects, knowledge-base
documents, vector entries, pending/convergence items, generation records) — no fictional stores. Two phases: logical
unretrievability from the next request, then physical removal, each recorded in a content-free deletion ledger.

### 4.7 ADR-007 — freshness evidence
`core/freshness.py`: builds the claim the system is entitled to make — proven watermark per class, global conservative
floor, pending count, oldest pending age, last completed reconciliation, window state. Queue depth and processing
latency are captured separately as operational metrics and never presented as freshness proof.

### 4.8 ADR-008 — repair and rebuild
`change/rebuild.py`: builds a replacement generation for a partition from authority, verifies it against the export and
the Episode 02 eligibility suite, promotes it, and retires the old one. The serving generation stays available if the
replacement fails verification.

## 5. As-built decisions

Recorded as they were made, each against the frozen decision it rests on. None changes the approved architecture.
**AB-1 is the one with observable request-path behaviour and is raised for confirmation.**

| ID | Decision | Basis | Why it was not obvious |
|---|---|---|---|
| **AB-1** | **Conservative mode withholds.** When completeness cannot be proven for a safety-critical class — no watermark has ever been established, or the last reconciliation is older than its window — the request path withholds (`WITHHELD_UNKNOWN_STATE`, detail `COMPLETENESS_NOT_PROVEN`) rather than answering on an unprovable claim. An unreadable convergence store withholds as `WITHHELD_CONVERGENCE_UNAVAILABLE`. | ADR-002, serving input 3: "if the watermark is older than its target, the system enters conservative mode for safety-critical classes"; ADR-007: "beyond the approved window the class enters conservative mode … safety-critical content is withheld rather than served on an unprovable claim" | The request-time status check already satisfies FRS-002 for every *retrieved* candidate, so conservative mode could have been read as evidence-only. It is implemented literally instead, which makes the watermark load-bearing at request time and FX-3 a visible safety event rather than only a reporting one. The cost is real: a deployment answers nothing until its first reconciliation pass completes, and the harness must reconcile after loading fixtures. **Direction:** this machinery can only ever *withhold*. It never makes content available that eligibility would have refused (SEC-001; §16) |
| **AB-2** | A change applies when the authoritative **status** differs at the same version, not only when the version is newer | ADR-004 · FRS-004 | Supersession does not edit the document, so it does not bump the version. Treating it as a duplicate left the document pending for ever while its derived copies kept serving — a silent non-convergence, found by a test written before the code was re-read |
| **AB-3** | A deletion reaches the physical phase only when **every** copy in the derived-copy graph is proven removed; a partial result stays logical, naming what is outstanding | ADR-006 · §11 | The obvious implementation checks the copies the caller happened to report, which would let "retrieval no longer returns it" pass as "deletion complete" |
| **AB-4** | Episode 02's separate ingestion function is **removed**; the change applier is the single writer of derived retrieval state, and the initial load is simply the first change | ADR-004 | Keeping both would give derived state two writers, so ordering and idempotency could not be proved in one place |
| **AB-5** | The notifier's IAM policy permits writes only to `PENDING#` keys, the applier's to everything **except** `WATERMARK#`, and only the reconciler may write a watermark | ADR-003 · §7 | "A notification must never advance the watermark" is a rule in the code; as a permission it is also true of anything that ever runs as those components. (The condition cannot constrain `Scan`, so reads are separate, unconditioned statements) |
| **AB-6** | A document whose classification record is invalid, or all of whose sections are special category, is recorded in derived state as `QUARANTINED` at that version — a terminal outcome, not a pending change | ADR-002 · CTL-007 · CTL-009 | The corpus deliberately contains four such records. Treating "nothing may be indexed" as a failed application left them pending for ever, and reconciliation re-queued a repair that could never succeed — which would eventually have pushed the whole system into conservative mode for a reason that is not a fault |
| **AB-7** | A rebuild at an unchanged authoritative version does not retire "the previous generation", because it *is* that generation | ADR-005 · ADR-008 | Retirement deletes a generation's derived copies. Rebuilding in place would have deleted the copies just written and verified — visible only as an empty index after a successful-looking rebuild |
| **AB-8** | The change role additionally holds `bedrock:StartIngestionJob` and `bedrock:AssociateThirdPartyKnowledgeBase` | Observed platform behaviour (first deployment, 2026-09-16) | Writing a document into a **custom** data source is denied without them, although neither name describes the call being made and no ingestion job or third party is involved. Found from CloudTrail after every document failed with `AccessDeniedException`; Episode 02's working role carries the same pair. **This is a measured platform requirement, not an architectural decision** |
| **AB-9** | A failed change records the AWS error code and the operation that raised it, and logs one line per failed document | FRS-004 · OPS-001 · §18 | The first implementation recorded only the exception class name, so "recorded as failed" could not say *what* failed: diagnosing AB-8 needed CloudTrail because the system had discarded the reason at the point of failure. The code and operation name carry no document content |
| **AB-10** | Removing a retired generation's documents is **eventually consistent**: for a few seconds after a switch, both generations can still be retrieved | Observed platform behaviour (baseline run, 2026-09-16) · ADR-005 | Measured, not assumed: a request during that window retrieved the same section at two versions. **The safety property did not lag** — the request path refused to mix versions and withheld (FRS-003 held, observably). Only *availability* lagged. So the window is contained by design rather than by timing, and a test asserting availability must wait for removal while a test asserting safety must not |
| **AB-13** | Deletion walks **every** generation — serving, retired or otherwise — and **proves** each derived copy absent by reading the stores back, rather than inferring absence from a generation's recorded state | ADR-006 · §11 · AB-3 | Found in the baseline: after AB-11's sweep had marked every generation RETIRED, `_remove` skipped them all, so `_delete_generation` never ran and the ledger recorded only 2 of 5 copies proven removed — while the content was in fact gone. Removal had happened; *proof* of removal had not. Retirement records an intention, not a fact about the stores. This is the §11 concern from the opposite direction, and AB-3 was right to refuse to call the deletion complete |
| **AB-12** | A deleted document is brought back by a **newer authoritative version**; only a change that is not newer is refused as `AFTER_DELETE` | ADR-004 clause 4 · FRS-005 · FRS-007 | The first implementation treated deletion as terminal against *every* later change, implementing only the first half of the clause ("cannot be reinstated by a late change") and omitting the second ("only a new authoritative record can bring content back"). Found in the baseline: D-01, D-02 and D-08 sat with authority at `IN_FORCE` v6/v4/v6 and derived state at `DELETED` v5/v2/v4, permanently divergent — each reconciliation pass found the drift, requested a repair, had it refused, and recreated the pending entry, so the system could never converge and never escalated. FRS-005 is unaffected: a late, duplicate or replayed change is still refused, because it is not newer |
| **AB-11** | Retirement **sweeps** every generation of a document except the one now serving, evaluated at switch time — it does not retire a "previous" remembered from when the build began | ADR-005 · FRS-003 | Found in the baseline: D-13 held **two generations marked SERVING**, with the older one's chunk and section object still present and retrievable. A build takes seconds to minutes, and the notifier's applier and a reconciliation repair can both act on one document, so the generation serving at switch time is often not the one read at build time — and retiring the stale one leaks the live one indefinitely. The request path contained the leak (it withheld on the version mismatch rather than mixing versions), but containment is not removal. Sweeping also makes retirement idempotent and self-healing: a leak left by any earlier concurrency is cleared the next time that document is applied |
| **AB-16** | **Found as a defect (2026-09-16). Retirement may take only generations provably OLDER than the one that won promotion.** `_retire_others()` skipped a generation only when it was the one being promoted or already `RETIRED`, so it also swept generations **newer** than that — destroying the derived copies of a concurrent promotion that had already advanced beyond it | ADR-005 · FRS-003 · AB-11 · AB-14 | Found by FX-3 and **proved on the deployment, not inferred** — the audit records the overtaking directly: `16:23:44 applied D-06 v12, retired ["D-06#g11", "D-06#g13"]` then `16:23:48 applied D-06 v13, retired ["D-06#g12"]`. A build writes `put_generation(g, VERIFIED)` before its switch, so a slower applier finishing v12 saw the in-flight g13, deleted its section object and knowledge-base document, and marked it retired; the v13 applier then switched g13 to SERVING. **The deterministic reproduction showed the blast radius is wider than the production trace alone suggested: a newer generation that has ALREADY promoted to SERVING is destroyed too** — the sweep's only exemptions were the promoted version itself and rows already marked RETIRED, so a newer generation was unprotected in every state. The result on the canonical environment: **D-06 serving `g13` with `D-06-S1-g13` still INDEXED and `sections/D-06/g13/S1.txt` gone**. Reconciliation compares authoritative version against reflected version, so it cannot see a missing section object — the drift is invisible to the mechanism that exists to find drift. **AB-14 correctly did not fire:** 11→12→13 are forward promotions, and AB-14 governs which generation may *become* serving, not which artefacts a completing operation may *destroy*. AB-11 closed the converse hazard — a live generation being leaked — and its sweep is what made this one reachable. Observed **three times** (11:47:12, 16:10:14, 16:23:44), one of them inside the accepted composite-baseline window, whose assertions nonetheless passed and whose environment was afterwards proved `CANONICAL CLEAN STATE`. **Invariant violated:** an operation promoting version N may retire only generations strictly older than N. **Repair:** a pure `generations.may_retire(candidate, promoted)` rule placed beside `switch()` at the shared promotion/retirement boundary, consumed by the single `_retire_others()` choke point that the incremental apply, reconciliation repair, operator repair and rebuild all funnel through — one definition, not four copies. The sweep's skip conditions become "already RETIRED" **or** "not strictly older"; nothing else changed, no ADR was touched, monotonicity was not weakened and no document was special-cased. **Regression coverage** (`RetirementNeverDestroysANewerGeneration`, four tests asserting destructive consequences rather than list membership): a newer VERIFIED generation survives an older operation's sweep; a newer already-SERVING generation likewise; genuinely older generations are still retired (AB-11's case, unchanged); and the whole sequence through the real `apply_one` path. All four failed against the unrepaired implementation — three on the destructive consequences — and pass after it. **This is not a case AB-11 or AB-14 covered:** AB-11 stopped a leaked OLDER generation staying retrievable, AB-14 governs which generation may BECOME serving, and AB-16 is the converse — which artefacts a completing operation may DESTROY |
| **AB-14** | **Found as a defect (2026-09-16) and fixed. The finding below is preserved exactly as it was recorded.** The rebuild path applied whatever authority currently says **without the ordering decision**: `rebuild.run()` calls `applier._build_and_switch()` directly and never calls `change_apply.decide()` | ADR-008 clauses 1–2 · ADR-004 clause 5 · FRS-005 · CTL-032 | Found while designing FX-2, and **proved on the deployment, not inferred**: with authority regressed to an older version, the applier refused it — `skipped: [{decision: OLDER, incoming_version: 1, reflected_version: 2}]`, derived state unmoved — while a rebuild of the same document **rebuilt the older generation and switched to it**, moving reflected state backwards v2→v1 (and again v4→v3 at tight timing), recreating the retired generation's section object and re-indexing its knowledge-base document. ADR-008 clause 2 requires operator reprocessing to use "the same path, not a special one"; ADR-004 clause 5 states a repair "can never move a document backwards"; clause 6 lists "the current state may reflect an older authoritative version" as a *trigger for* rebuild, which this path can therefore create. Whether this is a defect or correct behaviour turns on a question that needed an explicit decision: rebuild means "match current authority", and if authority genuinely says v1 then serving v1 is arguably right. FRS-005's own wording covers a late, duplicate or replayed **change** — not authority itself moving backwards. **Resolution (authorised narrowly for AB-14; no frozen architecture changed):** monotonicity is now enforced as an invariant over **transitions of derived state**, at the single promotion boundary every mechanism shares. `generations.switch()` takes the currently-serving state as a **required** argument and refuses any promotion `change_apply.may_promote()` rejects; `_build_and_switch` reads that state **at switch time** — not at the start of the build, which the ADR-005 / AB-11 lesson says is already stale — and removes the generation it has just built before refusing, so a refused promotion leaves no copies behind. `may_promote()` is defined in terms of the existing `decide()`, so monotonicity has one definition rather than a second copy bolted onto rebuild; promotion is allowed for `APPLY` and `DUPLICATE` (a rebuild at the version already serving stays idempotent) and refused for `OLDER` and `AFTER_DELETE`. Requiring the serving state as an argument is what makes a future repair or rebuild path hard to write without confronting the invariant. Covered by regression tests A–I: incremental replay, reconciliation repair, operator repair and rebuild each refused; forward promotion, same-version rebuild, canonical rebuild, retirement and tier routing each unchanged |
| **AB-15** | A failed change or rebuild records **where** it failed — stage, reason, attempted version, serving version, generation identity, bounded message and timestamp — not merely the exception class | FRS-004 · OPS-001 · §18 · AB-9 | AB-9 kept the AWS code and operation, which is enough for an SDK error and nothing for a local one. Both `RuntimeError`s in the build path therefore recorded the same four fields, and when FX-2's replay failed the evidence could not say which raise fired; the deployment's logs were destroyed with its stack during a correct cleanup before anyone could ask. The two raises are now `ChangeApplicationError` — a `RuntimeError` subclass, so every caller's behaviour is unchanged — carrying `stage` (`verify` / `index`), a reason code, the generation and both versions. The message is capped at 200 characters and stripped of line breaks, and the change path's exceptions are raised either by this module or by the SDK, so none carries document text (asserted by test). The reconciler keeps its `failed` class-name field unchanged for existing readers and records the diagnosis beside it |
| **AB-17** | **Found as a defect (2026-09-18), fixed, and validated against AWS.** A continuously divergent incident had its pending observation time RESET by every reconciliation pass, so the freshness window could never expire; the implementation also had no retry accounting and no escalation transition. The corrected implementation **preserves the incident clock**, **counts real application attempts**, and **raises a deduplicated, operator-observable alert** when the frozen window is breached. | FRS-004 · FRS-008 · OPS-001 · NFR-003 · ADR-007 clause 3 · CTL-035, CTL-036 | Reconciliation wrote `started_at` into every repair it requested, so a change diverging for hours looked each hour as though it had just been noticed and `oldest_pending_age_seconds` fell back to 0 — reproduced before any edit by driving the real `reconciler.run()` three times. **AB-12 had already recorded the SYMPTOM without naming the mechanism** — *"each reconciliation pass found the drift, requested a repair, had it refused, and recreated the pending entry, so the system could never converge and never escalated"* — and this is the second half of that sentence; AB-12 itself is unchanged. A second, narrower defect was found while proving the first: reconciliation also **recomputed the pending CLASS** from `change_class_for(None, state)`, which structurally cannot return a reclassification, so a `reclassify_up` incident (safety-critical, zero-second window) was silently downgraded to `new_version` (four hours) BEFORE the breach was evaluated in the same pass. That was not merely an alerting defect: `conservative_mode` consults SAFETY_CRITICAL_CLASSES only, so the downgrade moved the request path from WITHHOLDING to SERVING. The class is now fixed when the incident is CREATED and preserved until it converges, with **no severity ordering invented** — none was needed, and none exists in frozen material. A third defect was self-inflicted and caught by its own regression: `_escalate` wrote back a pending snapshot taken before the repair loop invoked the applier, erasing the genuine attempt just recorded; it now re-reads and never resurrects a converged entry. **AWS validation (2026-09-18):** `noticed_at` held at 09:20:48Z across three passes, `attempts` 1 → 2 → 3 from real applier invocations, breach `{'reclassify_up': ['D-04']}`, `escalated_at 09:23:00Z` persisted after emission, alarm OK → ALARM at 09:24:23Z, no duplicate transition on the next pass, and convergence cleared the incident. Mutation proof 7 of 7 locally. |

## 6. Scale (§17)

The educational deployment uses a **reduced corpus** — about a dozen synthetic documents — and states that plainly.
Measured results are educational observations, never production benchmarks, and never extrapolated to the fictional
client's 180,000 documents.

## 7. What this implementation does not build

- No script, storyboard, media or publishing assets.
- No commercial reference package.
- No production hardening beyond what the taught controls require.
- No new authorisation behaviour: Episode 02's model is preserved, not extended.
