# Test Harness Design and Detailed Validation Matrix — Kestrelmoor Knowledge Assistant

**Stage:** implementation, as built · **Date:** 2026-09-15 · **Status:** design accepted; harness implemented in `harness/`

**Test definitions** live in [VALIDATION_PLAN.md](VALIDATION_PLAN.md) (31 tests). This document specifies how the harness
runs them, what it observes, and what evidence it produces.

**Results** are recorded per run under `07-evidence/`; differences from this design are listed in
`../05-implementation/IMPLEMENTATION_DESIGN.md` §14.

## 1. Observation points and canary strategy

**Canaries:**
- **Format:** `CANARY-<LABEL-OR-KIND>-<SCOPE-OR-TOPIC>-<SUFFIX>` — unique per section, listed in the synthetic data
  model.
- **Oracle:** `harness/canaries.py` generates the oracle (canary → document, section, label, scope, eligible personas)
  from the fixtures and the eligibility rule.
- **Cross-check:** a unit test compares the generated oracle with the hand-written table in the synthetic data model §3.
  The two must agree.

**The scanner** searches every observation point for every canary a persona is **not** eligible for:

| Channel | How it is read |
|---|---|
| Retrieved chunks | Audit item `retrieval[]` (identifiers, labels, scopes), plus the chunk IDs resolved to canaries through the inventory |
| Answer and citations | Response body |
| Source metadata and error bodies | Response body and headers |
| Audit records | Audit store scan |
| Operational logs | CloudWatch Logs `FilterLogEvents` for `CANARY-` over the run window |
| Tier contents | Inventory: vector metadata listing per tier (text is stored as non-filterable metadata), section bucket listings |

**Positive tests** additionally require each **eligible** target canary to appear.

## 2. Detailed validation matrix

| Area | Test | Personas / fixtures | Observation points | Evidence file | Pass rule |
|---|---|---|---|---|---|
| Eligibility | TST-ELG-001 | P-01; D-01 | Retrieved, answer, citations | `TST-ELG-001.json` | D-01 canary retrieved and cited |
| Eligibility | TST-ELG-002 | P-02; D-03 §4 | Retrieved, answer, citations | `TST-ELG-002.json` | BID-ORION canary retrieved and used |
| Eligibility | TST-ELG-003 | P-02 then P-01, P-03–P-07 with identical questions; D-03 §4, D-14 | All channels; audit `tiers_called` | `TST-ELG-003.json` | No BID-ORION canary for ineligible personas, including immediately after P-02's identical question |
| Eligibility | TST-ELG-004 | P-01; D-03 §1–4 | Retrieved; inventory provenance | `TST-ELG-004.json` | Lessons canary present; pricing canary never retrieved |
| Eligibility | TST-ELG-005 | P-04 precondition, then P-03; D-07 | All channels | `TST-ELG-005.json` | No SEC-SIGNALLING canary for P-03 |
| Eligibility | TST-ELG-006 | P-05, P-06 preconditions, then P-07; D-04 §2, D-05 | All channels; `tiers_called` | `TST-ELG-006.json` | No case canary; restricted tier not called for P-07 |
| Eligibility | TST-ELG-007 | P-05, P-06; D-04 §2, D-05 | All channels | `TST-ELG-007.json` | Each receives only their own case |
| Eligibility | TST-ELG-008 | P-01; restricted-only topic and a non-existent topic | Response bytes | `TST-ELG-008.json` | Responses identical |
| Eligibility | TST-ELG-009 | P-05 (restricted tier called) asks HR-2031; P-02 (shared tier) asks D-08 and D-07 topics | Retrieved; `tiers_called`; constraint hashes | `TST-ELG-009.json` | Zero HR-2031, FIN-REPORTING and SEC-SIGNALLING canaries although the tier was queried |
| Security | TST-SEC-001 | Invalid tokens | Status codes; audit absence | `TST-SEC-001.json` | 401 each; no audit item created |
| Security | TST-SEC-002 | P-01 with forged domain and case in body, query, headers, question and extra token claims | Audit decision versions; all channels | `TST-SEC-002.json` | Decision equals the grants store |
| Security | TST-SEC-003 | P-01 prompt attacks; D-12 | Constraint hash vs baseline; all channels | `TST-SEC-003.json` | Hash identical; no ineligible canary |
| Security | TST-SEC-004 | Harness test role without permissions; query and ingestion roles | Call outcomes | `TST-SEC-004.json` | Only the query role can `Retrieve`; each tier's section bucket readable only by its own knowledge-base role |
| Security | TST-SEC-005 | Fault: deny read on the grants store to the query role; P-01, P-02, P-05 | Audit `tiers_called`, outcome; response bytes | `TST-SEC-005.json` | **Zero tier calls**; uniform failure; outcome `REFUSED_AUTHORIZATION_UNAVAILABLE`; fault removed after |
| Security | TST-SEC-006 | P-08, P-09 | Audit; response | `TST-SEC-006.json` | No tier calls; uniform failure |
| Security | TST-SEC-007 | Fault: one D-03 §4 chunk's attribute set to INTERNAL (test-only re-ingest of that section with a wrong attribute) | Audit verification; `generation.invoked` | `TST-SEC-007.json` | Withheld; mismatch recorded; no generation |
| Data | TST-DATA-001 | D-09 | Quarantine report; inventory | `TST-DATA-001.json` | Quarantined; canary absent from both tiers |
| Data | TST-DATA-002 | D-10, D-11, D-15 | Quarantine report; inventory | `TST-DATA-002.json` | All quarantined; canaries absent |
| Data | TST-DATA-003 | D-14 | Inventory; P-01, P-02 retrieval | `TST-DATA-003.json` | Indexed as CONFIDENTIAL BID-ORION |
| Data | TST-DATA-004 | D-04 §3; all personas | Inventory; audit; logs; answers | `TST-DATA-004.json` | Special-category canary absent everywhere |
| Data | TST-DATA-005 | Whole corpus | Inventory | `inventory.json` + `TST-DATA-005.json` | Every chunk's attributes equal its record; no chunk less restrictive than its document |
| Data | TST-DATA-006 | Whole corpus | Tier inventories; cache inventory | `TST-DATA-006.json` | RESTRICTED only in the restricted tier; none in the shared tier; no cache resources or entries |
| Change | TST-CHG-001 | P-02; revocation in the grants store (token unchanged) | Audit decision versions; all channels | `TST-CHG-001.json` | After revocation: no BID-ORION retrieval; new `grants_version` |
| Change | TST-CHG-002 | D-13 record changed to CONFIDENTIAL OPS-LEADERSHIP without re-ingest; P-01, P-07 | Audit verification | `TST-CHG-002.json` | Withheld for both until re-ingest (expected); restore |
| Observability | TST-OBS-001 | Whole run | Audit store; logs | `canary-scan.json` + `TST-OBS-001.json` | No canary; no question text or hash; decisions present |
| Observability | TST-OBS-002 | Three recorded requests; reports | Reconstruction; reports | `reconstruction.json` + `TST-OBS-002.json` | Reconstruction equals outcomes; reports list quarantined fixtures and the mismatch |
| Scale | TST-SCALE-001 | P-10 (40 grants); over-limit synthetic persona | Audit bytes and latency; outcome | `TST-SCALE-001.json` | P-10 retrieves D-08 only among CONFIDENTIAL; over-limit refused before the call |
| Repeatability | TST-OPS-001 | Fresh clone | Run log; results | `TST-OPS-001.json` | Unattended; results match; cleanup verified |
| Sensitivity | TST-SEN-001 | Variant `eligibility-removed` | See §3 | `sen-eligibility/verdict.json` | Variant FAILs, normal PASSes |
| Sensitivity | TST-SEN-002 | Variant `labels-corrupted` | See §3 | `sen-labels/verdict.json` | Variant FAILs, normal PASSes |
| Sensitivity | TST-SEN-003 | Variant `claims-as-grants` | See §3 | `sen-claims/verdict.json` | Variant FAILs, normal PASSes |

## 3. The three failure experiments

**Every experiment follows this sequence:**
1. **Baseline:** run the target tests on the normal deployment → must PASS; bundle `baseline/`.
2. **Fault introduced:** deploy the variant stack (`Variant=<name>`, its own resources); load the same fixtures.
3. **Expected FAIL:** run the target tests against the variant → must FAIL for the predicted reason; bundle `variant/`.
4. **Observed evidence:** record the retrieval-layer leak, the verification behaviour and the audit outcomes.
5. **Fault removed:** delete the variant stack; verify that no variant resource remains; bundle `cleanup/`.
6. **Restored PASS:** re-run the target tests on the normal deployment → must PASS; bundle `restored/`.
7. **Verdict:** PASS only if 1, 3, 5 and 6 all hold. If the variant's target tests pass, the tests are blind → STOP.

### Experiment 1 — eligibility constraint removed (TST-SEN-001)
- **Security assumption tested:** the retrieval boundary is what keeps ineligible sections out of retrieval.
- **Fault:** `sensitivity/eligibility_removed.py` replaces the gateway's constraint builder so that both tiers are
  queried **without** a constraint for every requester. The decision is still computed, and verification is unchanged.
- **Target tests:** TST-ELG-003, TST-ELG-005, TST-ELG-006, TST-ELG-009.
- **Expected:**
  - **Retrieval-layer leak:** every target FAILS at the retrieval layer; the audit `retrieval[]` lists BID-ORION,
    SEC-SIGNALLING, SI-0417 and HR-2031 chunks for ineligible personas.
  - **Containment:** verification then finds chunks ineligible under the decision → **withholds**, and
    `generation.invoked = false`.
- **What it proves:**
  - the tests observe the retrieval boundary;
  - **withholding is detection and containment after retrieval, not safety** — ineligible content had already crossed
    into the query function's memory.

### Experiment 2 — label propagation corrupted (TST-SEN-002)
- **Security assumption tested:** section labels reach every chunk intact.
- **Fault:** `sensitivity/labels_corrupted.py` replaces the section processor so that every section inherits the
  **document** label, and routing follows that corrupted label. D-03 §4 is indexed as INTERNAL. D-04 §2 is indexed as
  INTERNAL in the **shared** tier.
- **Target tests:** TST-ELG-004, TST-DATA-005, TST-DATA-006.
- **Expected:**
  - **Retrieval:** TST-ELG-004 FAILS — P-01's retrieval includes the pricing chunk, **so retrieval does expose the
    corruption before generation**.
  - **Inventory:** TST-DATA-005 FAILS (chunk attributes ≠ record); TST-DATA-006 FAILS (a RESTRICTED section sits in the
    shared tier).
  - **Verification:** compares the chunk (INTERNAL) with the current record (CONFIDENTIAL BID-ORION) → **mismatch →
    withheld**.
- **What it proves:**
  - the tests detect wrong **metadata**, not only a missing filter;
  - the pre-generation check contains label corruption before generation.

### Experiment 3 — stale token claims used as grants (TST-SEN-003)
- **Security assumption tested:** current fine-grained entitlements come from the authoritative grants store, not from
  authentication claims.
- **Fault:** `sensitivity/claims_as_grants.py` replaces the grants reader so that domains and cases are read from the
  token's `cognito:groups` claim. At fixture load, groups mirror the grants.
- **Target test:** TST-CHG-001.
- **Sequence:** P-02 obtains a token → revoke BID-ORION in the grants store and remove the group → ask again **with the
  same token**.
- **Expected:** the variant still retrieves BID-ORION → TST-CHG-001 FAILS; the normal deployment refuses → PASS.
- **What it proves:** authentication claims describe the identity at sign-in; they are not a current authorization
  source.

## 4. Fault injection without code paths in the normal build

| Fault | Mechanism | Removed by |
|---|---|---|
| Grants store unavailable (TST-SEC-005) | Harness confirms a clean baseline, then attaches a temporary explicit Deny on the grants table to the query role and waits (up to 15 minutes) until a probe is refused; if the fault never takes effect the test is recorded as ERROR (inconclusive), never as a control result | Harness detaches it and waits until a probe is answered again; the propagation time is recorded |
| Wrong chunk attribute (TST-SEC-007) | Harness re-ingests one section inline with label INTERNAL through the operator's own ingestion permission (a test-only path, not the ingestion function) | Harness invokes the ingestion function for the document again |
| Upward reclassification (TST-CHG-002) | Harness updates the classification record and version | Harness restores and re-ingests |
| Revocation (TST-CHG-001) | Harness removes the grant and bumps `grants_version` | Harness restores |

The normal package contains no switch for any of these faults. Variants exist only in their own stacks.
