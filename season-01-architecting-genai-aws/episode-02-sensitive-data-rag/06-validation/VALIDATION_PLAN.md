<!-- template: tla-validation-plan/1 -->
# Validation Plan — Kestrelmoor Knowledge Assistant

**Stage:** architecture engagement definition → implementation design · **Status:** accepted (2026-09-15) · **Date:** 2026-09-15

**No test is implemented or run.** Results will be recorded in the [traceability matrix](TRACEABILITY_MATRIX.md).

**Deployment is not validation.** "The filter exists" shows nothing.

## 1. Principles

1. **Observe at the layer that decides.** The primary observation for every eligibility test is the audit record's
   retrieved-chunk list (identifiers, labels, scopes), then answers, citations, metadata, errors and logs. A clean answer
   never proves clean retrieval.
2. **Canaries make leaks mechanical.** Every restricted section has a unique canary ([synthetic data](../03-architecture/SYNTHETIC_DATA_MODEL.md)).
   A test fails if any ineligible canary appears in any channel.
3. **Not vacuous.** Negative tests target restricted sections that exist and share the topic with eligible ones. A
   precondition run with an eligible persona confirms each target is retrievable.
4. **Positive tests guard against over-blocking.** A control that blocks the entitled is broken.
5. **Every critical negative test is seen to fail** when its control is removed or corrupted (section 4).
6. **Synthetic data only** (ASM-010). The run is repeatable and unattended from a fresh copy (OPS-003).
7. **The tier is not the authorization boundary.** Every tier holds more than one scope; negative tests include requesters
   who are correctly routed to a tier but lack the scope (TST-ELG-009).
8. **No authoritative current grants = no retrieval**: outage and unknown-person tests expect zero search calls.

## 2. Test levels

`L0` static and unit (eligibility rule, taxonomy validation, section chunking — no cloud) · `L1` configuration intent
(permissions, logging settings) · `L2` deployment smoke · `L3` requirement acceptance · `L4` change and failure ·
`L5` fresh-copy run.

## 3. Tests

| ID | Verifies | Level | Type | Setup | Action | Expected result | Evidence captured | Sensitivity run | Cleanup |
|---|---|---|---|---|---|---|---|---|---|
| TST-ELG-001 | BUS-001, FUN-001 | L3 | positive | Corpus ingested | P-01 asks about SMP-12 fault procedure | Answer uses `CANARY-INT-SMP12` content; section citation to D-01 | Audit retrieved list; response | — | None |
| TST-ELG-002 | FUN-002 | L3 | positive | Corpus ingested | P-02 asks about Orion commercial position | `CANARY-BID-ORION-PRICING-7Q3` retrieved and used; citation D-03 §4 | Audit; response | — | None |
| TST-ELG-003 | SEC-001, SEC-004 | L3 | negative | Precondition: TST-ELG-002 retrieved the target | P-01, P-03, P-04, P-05, P-06, P-07 each ask the same Orion pricing questions | No BID-ORION canary in retrieved list, answer, citations, metadata, errors or logs | Audit retrieved list per persona; canary scan | TST-SEN-001 must make this fail | None |
| TST-ELG-004 | FUN-004, DATA-003 | L3 | negative + positive | D-03 ingested with section marks | P-01 asks about Orion lessons learned and Orion pricing | Lessons (`CANARY-INT-ORION-LESSONS`) answered; §4 never retrieved | Audit; response; chunk provenance | TST-SEN-002 must make this fail | None |
| TST-ELG-005 | SEC-001 | L3 | negative | Precondition: P-04 retrieves D-07 | P-03 (finance) asks about controller maintenance costs and weaknesses | No `CANARY-SEC-SIG-VULN-3F` in any channel | Audit; canary scan | TST-SEN-001 | None |
| TST-ELG-006 | SEC-001, SEC-006 | L3 | negative | Preconditions: P-05 retrieves D-04 §2; P-06 retrieves D-05 | P-07 (director) asks about the Northfield incident witnesses and case HR-2031 | No SI-0417 or HR-2031 canary; restricted tier not called for P-07 | Audit (tier calls, retrieved list) | TST-SEN-001 | None |
| TST-ELG-007 | FUN-002, SEC-006 | L3 | positive + negative | Corpus ingested | P-05 asks about SI-0417 witnesses and HR-2031; P-06 asks the reverse | Each receives only their own case canary; never the other's | Audit; response | — | None |
| TST-ELG-008 | FUN-003 | L3 | negative | Topic exists only in restricted content; a second topic exists nowhere | P-01 asks both questions | The two responses are identical in shape and wording; no citation, count, title or hint | Response comparison | — | None |
| TST-ELG-009 | SEC-001, SEC-006 | L3 | negative | Restricted tier holds SI-0417 and HR-2031; shared tier holds BID-ORION, FIN-REPORTING and SEC-SIGNALLING | P-05 (assigned SI-0417, so the restricted tier **is** queried) asks about HR-2031; P-02 (BID-ORION, shared tier queried) asks about the finance pack and the vulnerability assessment | Zero HR-2031, FIN-REPORTING or SEC-SIGNALLING canaries: being routed to the correct tier grants nothing; the constraint decides | Audit (tier calls, constraint hash, retrieved list); canary scan | TST-SEN-001 must make this fail | None |
| TST-SEC-001 | SEC-002 | L3 | negative | Deployment ready | Missing, expired, wrongly signed and foreign-audience tokens | Refused at edge; no policy decision point or search call | Edge and audit records | — | None |
| TST-SEC-002 | SEC-003 | L3 | negative | Registry: P-01 has no domains | P-01 sends `domain=BID-ORION` and `case=HR-2031` in body, query, headers, question text, and a token with extra group claims | Decision equals the registry (INTERNAL only); no restricted canary | Audit decision and source versions | — | None |
| TST-SEC-003 | SEC-005 | L3 | negative | D-12 contains injected instructions | P-01 asks prompt-attack questions and a question retrieving D-12 | Constraint hashes identical to a baseline question; no ineligible canary | Constraint hashes; audit | — | None |
| TST-SEC-004 | SEC-009, SEC-013 | L3 | negative | Deployment ready | Call both search tiers directly with the learner's normal credentials and with the query-component identity | Denied for every principal except the gateway | Denied-call records | — | None |
| TST-SEC-005 | SEC-007, NFR-003 | L4 | failure | Read access to the entitlement source denied to the query component (test fault) | P-01, P-02 and P-05 ask INTERNAL, CONFIDENTIAL and RESTRICTED questions | **No search call to either tier** (audit shows none); safe uniform failure that mentions no restricted content; content-free audit event naming the unavailable source | Audit; response | — | Restore the source |
| TST-SEC-006 | SEC-007 | L3 | negative | Registry has no record for P-09; P-08 is INACTIVE with a stale grant | P-08 and P-09 ask INTERNAL and BID-ORION questions | P-08 and P-09: no search call; uniform failure; no canary of any label | Audit | — | None |
| TST-SEC-007 | SEC-008 | L4 | failure | Test fixture: one D-03 §4 chunk's indexed label altered to INTERNAL directly in the shared tier (test-only path) | P-01 asks Orion pricing | Answer withheld; security event naming the mismatch; uniform response | Security event; audit | — | Re-ingest D-03 |
| TST-DATA-001 | DATA-005, SEC-007 | L3 | negative | D-09 unlabelled | Ingest; P-01 asks about depot tooling | D-09 quarantined and reported; `CANARY-UNLABELLED-TOOLS` absent from both tiers | Ingestion report; tier inventory | — | None |
| TST-DATA-002 | DATA-001, DATA-005, SEC-007 | L3 | negative | D-10 misspelt label; D-11 CONFIDENTIAL without scope; D-15 lower-case `internal` (label matching is exact, SPK-E02-A C10) | Ingest; eligible and ineligible personas query | Both quarantined; canaries absent from both tiers | Ingestion report; inventory | — | None |
| TST-DATA-003 | DATA-002 | L3 | negative | D-14 text says "Classification: INTERNAL"; record says CONFIDENTIAL BID-ORION | Ingest; P-01 and P-02 ask | Indexed as CONFIDENTIAL BID-ORION; P-01 never retrieves it; P-02 does | Chunk provenance; audit | — | None |
| TST-DATA-004 | DATA-004, CMP-001 | L3 | negative | D-04 §3 marked special-category | Ingest; every persona, including P-05, asks about the incident's medical details | `CANARY-SPECIAL-SI0417-MED` absent from both tiers, embeddings inputs, model inputs, answers and logs | Tier inventory; audit; log scan | — | None |
| TST-DATA-005 | DATA-003, DATA-007 | L3 | positive | Corpus ingested | Inventory every chunk | Every chunk states document, section, label, scope, record version; no chunk spans sections; no chunk less restrictive than its document | Inventory report | TST-SEN-002 must make this fail | None |
| TST-DATA-006 | DATA-006 | L3 | negative | Corpus ingested; answers produced by earlier tests | Inventory tiers and caches | Shared tier holds no RESTRICTED chunk; restricted tier only RESTRICTED; no cached answer built from CONFIDENTIAL or RESTRICTED content | Tier and cache inventory | — | None |
| TST-CHG-001 | SEC-010, SEC-003, BUS-002 | L4 | change | P-02 eligible for BID-ORION (TST-ELG-002 passed); P-02's token still carries a stale group claim | Revoke P-02's BID-ORION membership in the registry; P-02 asks again after the registry records it | No BID-ORION retrieval; decision shows the new registry version | Audit before and after | TST-SEN-003 must make this fail | Restore membership |
| TST-CHG-002 | SEC-011 | L4 | change | D-13 indexed as INTERNAL | Reclassify D-13 to CONFIDENTIAL OPS-LEADERSHIP in the classification record **without** re-indexing; P-01 asks about Northfield resilience | Answer withheld (verification), security event; P-07 (OPS-LEADERSHIP) is also withheld until re-index (expected, RR-04) | Audit; security events | — | Restore record; re-ingest |
| TST-OBS-001 | SEC-012, DATA-006 | L3 | negative | Whole validation run complete | Scan every audit record, log, trace and model invocation record for all canaries and for question text | No canary; no question text (keyed hashes only); decisions, labels and scopes present | Scan report | — | None |
| TST-OBS-002 | OPS-001, OPS-002 | L3 | positive | TST-ELG-003, TST-SEC-007 and TST-DATA-001 run | Reconstruct three decisions from audit records and stored versions; open the quarantine and mismatch reports | Reconstruction matches the observed outcomes; reports list D-09, D-10, D-11, D-15 and the TST-SEC-007 mismatch | Reconstruction output; reports | — | None |
| TST-SCALE-001 | NFR-001, NFR-002 | L4 | load / boundary | P-10 holds 40 domains including FIN-REPORTING; a synthetic persona holds enough grants to exceed the application's constraint budget, which sits below the lower observed platform limit (SPK-E02-A C6; build re-measurement) | P-10 asks about the month-end pack; the over-limit persona asks anything restricted | P-10 retrieves D-08 and no ineligible canary; over-limit persona refused (fail closed), never truncated; eligibility overhead recorded | Audit; timings | — | None |
| TST-OPS-001 | OPS-003 | L5 | repeatability | Fresh clone into a clean sandbox | Run preflight → deploy → ingest → full suite → cleanup | Suite completes unattended; results match; cleanup verified | Run log; results bundle | — | Verified cleanup |
| TST-SEN-001 | SEC-001, SEC-004 | L4 | sensitivity | **Separate throwaway deployment** with the gateway variant that omits eligibility clauses and queries both tiers for everyone | Run TST-ELG-003, TST-ELG-005, TST-ELG-006, TST-ELG-009 against the variant; then destroy it; re-run them on the normal system | Variant: all four **FAIL** at the retrieval layer (canaries retrieved), and verification **withholds** (detection, not safety). Normal: all four PASS. Verdict PASS only if both hold | Baseline, variant, cleanup and restored bundles; verdict | This is the sensitivity run | Destroy variant; verify cleanup |
| TST-SEN-002 | SEC-008, DATA-003 | L4 | sensitivity | **Separate throwaway deployment** with the ingestion variant that ignores section marks (document label applied to all chunks) | Run TST-ELG-004 and TST-DATA-005 against the variant; destroy; re-run on normal | Variant: TST-ELG-004 **FAILS** (D-03 §4 retrieved for P-01), TST-DATA-005 **FAILS** (provenance mismatch), verification **withholds**. Normal: PASS | Bundles; verdict | Sensitivity run | Destroy variant |
| TST-SEN-003 | SEC-010 | L4 | sensitivity | **Separate throwaway deployment** with the policy-decision-point variant that reads token group claims | Run TST-CHG-001 against the variant; destroy; re-run on normal | Variant: TST-CHG-001 **FAILS** (revoked P-02 still retrieves BID-ORION). Normal: PASS | Bundles; verdict | Sensitivity run | Destroy variant |

## 4. The experiments that must be able to fail

**Why three.** Episode 01 showed that one missing constraint makes the tests fail. Here there are three different ways
the eligibility boundary can be silently wrong, and each has its own experiment:

| Experiment | What is broken | What it proves about the tests |
|---|---|---|
| TST-SEN-001 · control removal | The eligibility constraint itself | The negative eligibility tests observe retrieval, not just answers |
| TST-SEN-002 · control corruption | Label propagation at ingestion | The tests detect wrong **metadata**, not only a missing filter |
| TST-SEN-003 · wrong authority | Where entitlements come from | The revocation test detects stale authorization |

**Rules for every experiment:**
- a separate deployment and separate tiers, never the normal system;
- the variant is destroyed, and cleanup verified;
- the normal system passes before and after;
- the verdict requires the variant to fail **and** the normal system to pass.

