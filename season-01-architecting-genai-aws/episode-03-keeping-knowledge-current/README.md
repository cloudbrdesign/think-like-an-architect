# Episode 03 lab — keeping a knowledge base current

**Kestrelmoor Rail Systems (fictional) · synthetic data only · your own sandbox AWS account · about 45 minutes**

## Episode objective

Watch a knowledge assistant stay safe while its index is wrong, and watch it put the index right.

Kestrelmoor's records system is the **authority**. The retrieval index is a **copy** built from it. Every change to a
record opens a window in which the copy is out of date. In this lab you will:

- keep a stale copy in the index, retrieve it, and see the assistant refuse it;
- see reconciliation find the divergence and repair it;
- break the application of a real change and watch it stay visible, be retried, escalate and recover.

## The architecture lesson

> **Events accelerate convergence. Authority determines truth. Reconciliation restores consistency.**

- A change notification makes the index catch up quickly. It cannot prove that nothing was missed, because a change
  that was never delivered is invisible to delivery.
- On every request, the assistant checks what it retrieved against the records system. A copy that is *present* is not
  necessarily *current*, so it can be retrieved and still refused.
- Only reconciliation reads the authority and compares it with the index. That comparison is what earns the claim that
  nothing is missing, and it repairs whatever it finds.
- A change that cannot be applied stays pending, keeps its original clock, is retried, and is escalated when it
  outlives its window. It is never silently lost.

Every document is in exactly one of four states: **known current**, **known pending**, **known gone** (superseded,
withdrawn or deleted), or **unknown**. Only *known current* is ever served.

## Prerequisites

- A **sandbox** AWS account that you control. Never point this lab at real records.
- Region **us-east-1**, with model access to **Amazon Titan Text Embeddings V2** and **Amazon Nova Micro**.
- **Model invocation logging switched off.** Preflight checks this, because otherwise prompts containing section text
  would be copied into logs.
- **Python 3.10+** with **boto3**, and AWS credentials available through the standard credential chain.
- An **AWS Budget with alerts**. Preflight reads it.

## Cost

Nothing in this lab is billed by the hour. Cost comes from embeddings, a few model calls, function invocations and
requests. **One complete run of both parts is expected to cost well under USD 0.50.** That figure is an estimate
derived from the dated prices in `05-implementation/COST_AND_CLEANUP.md`; only your bill confirms it, and billing lags
by about a day.

The real risk is leaving something running, not the cost. **Run the `lab-down` command for each part.** Each part
takes about five minutes to create, so do Part A and Part B in one sitting.

## Setup

From the episode folder:

```
cd 05-implementation
cp config/learner.env.example config/learner.env    # set TLA_EXPECTED_ACCOUNT and TLA_BUDGET_NAME
python3 scripts/tla_ops.py preflight                # models, region, logging, budget, leftovers
```

Every command confirms the account first, and it refuses to run if your credentials belong to a different account than
`TLA_EXPECTED_ACCOUNT`.

**Where commands run:**
- `lab-up` and `lab-down` run from `05-implementation/` (`python3 scripts/tla_ops.py …`).
- Every other command runs from `06-validation/` (`python3 -m harness …`).
- Every `lab-*` command acts on whichever lab part is running. A command that belongs to the other part refuses and
  tells you why.

---

## Part A — present is not current (delivery off)

**Why a separate deployment:** Part A needs a stale copy to *survive* a change. With notifications on, the index
catches up within seconds and there would be nothing to see. Switching notifications off on a running system is not a
reliable way to hold that window open. So Part A is **created without notifications**, and no event will ever tell the
index about your change.

| # | Do this | You should see | Why it matters |
|---|---|---|---|
| A1 | `python3 scripts/tla_ops.py lab-up delivery-off` | `READY`, 15 documents reflected, `notifications OFF since creation` | A working assistant whose index nobody will notify |
| A2 | `python3 -m harness lab-ask induction_ppe --as P-01` | D-02's sections retrieved, D-02 `KNOWN_CURRENT`, outcome `ANSWERED`, D-02 cited | The before-state: the document answers normally |
| A3 | `python3 -m harness lab-withdraw D-02` | status `IN_FORCE -> WITHDRAWN`, version unchanged, `nothing told the index` | Authority changes; the copy does not |
| A4 | `python3 -m harness lab-inspect D-02` | authority `WITHDRAWN`; index believes `IN_FORCE`; copies `PRESENT`; `DIVERGED` | **The copy exists.** Its label, scope and version still match |
| A5 | `python3 -m harness lab-ask induction_ppe --as P-01` | D-02's sections **retrieved**; D-02 `KNOWN_SUPERSEDED_WITHDRAWN_DELETED`; both copies `NOT_CURRENT`; outcome `WITHHELD_NOT_CURRENT` at `CTL-030`; model not invoked; nothing cited; and the summary line `=> COPY: PRESENT (retrieved D-02-S1, D-02-S2)   REQUEST: WITHHELD_NOT_CURRENT` | **The copy was not trusted.** The request asked authority, and authority said no |
| A6 | `python3 -m harness lab-reconcile` | diverged `D-02 (authority WITHDRAWN, index IN_FORCE)`; `D-02 REPAIRED`; confirmation pass `CONVERGED` | Reconciliation found what delivery never reported, and repaired it |
| A7 | `python3 -m harness lab-inspect D-02` | authority still `WITHDRAWN` (the record is retained); index `DELETED`; copies `ABSENT`; `Converged` | Authority keeps the record. The index no longer holds anything that could be retrieved |
| A8 | `python3 scripts/tla_ops.py lab-down delivery-off` | `nothing from this part remains` | End Part A before starting Part B |

**Explain it in one line:** *the copy existed; the copy was not trusted.*

Notice what did **not** happen in A5. Nothing notified the index, no one fixed the index first, and the copy matched on
label, scope and version. The refusal came from checking the authoritative status on that request.

---

## Part B — failure is visible, retried and escalated (delivery on)

**Why a separate deployment:** Part B needs a real change to travel the **normal** delivery path. Only the live
notifier classifies an upward reclassification, and that class has a **zero-second** window. Without delivery the same
change would be discovered later as a new version with a four-hour window, and nothing would escalate while you watch.

| # | Do this | You should see | Why it matters |
|---|---|---|---|
| B1 | `python3 scripts/tla_ops.py lab-up delivery-on` | `READY`, `notifications ON` | A healthy deployment with live delivery |
| B2 | `python3 -m harness lab-ask si0417_findings --as P-01` and `python3 -m harness lab-inspect D-04` | `ANSWERED`, D-04 cited; D-04 `In agreement` at v1 | The healthy starting state |
| B3 | `python3 -m harness lab-obstruct D-04` | source `REMOVED`; record, code, permissions and delivery unchanged | The only fault in this part: D-04's next build cannot read its text |
| B4 | `python3 -m harness lab-reclassify-up D-04` | `INTERNAL -> CONFIDENTIAL`, scope `SI-0417`, `v1 -> v2`; notification received, class `reclassify_up`; application `FAILED — AccessDenied on GetObject`; pending `YES … attempts 1` | A real change entered normal delivery and could not be applied |
| B5 | `python3 -m harness lab-incident D-04` | `change still PENDING`; window `0 s — BREACHED`; attempts 1; escalated `not yet`; alarm `OK` | The failure is visible, not lost |
| B6 | `python3 -m harness lab-reconcile` | diverged `D-04 (authority v2, index v1)`; `D-04 RETRY FAILED`; `ESCALATED on this pass — alert raised`; still pending `D-04` | The retry ran through the real path and failed again. The breach escalated |
| B7 | `python3 -m harness lab-incident D-04 --wait-for-alarm` | attempts `2`; **`noticed at` unchanged** and the age growing; escalated at a time; alarm `ALARM` | The retry did not reset the clock. The escalation reached monitoring |
| B8 | `python3 -m harness lab-unobstruct D-04` | source `RESTORED`; pending still `YES` | Removing the fault does not by itself apply the change |
| B9 | `python3 -m harness lab-reconcile` | `D-04 REPAIRED`; `already escalated; not raised again`; still pending `nothing`; `CONVERGED` | Recovery: the change is applied, and the incident clears without a second alert |
| B10 | `python3 -m harness lab-incident D-04` | `No open incident`; authority v2 `CONFIDENTIAL`, index v2 | Converged on the **new** authoritative state |
| B11 | `python3 scripts/tla_ops.py lab-down delivery-on` | `nothing from this part remains` | Leave nothing running |

**Explain it in one line:** *failure was not silently lost.*

---

## Cleanup

Run both of these, even if something went wrong part-way through:

```
cd 05-implementation
python3 scripts/tla_ops.py lab-down delivery-off
python3 scripts/tla_ops.py lab-down delivery-on
```

Each command removes the part's objects, stack and package bucket, then checks by name that nothing remains:
stacks, knowledge bases, vector stores, buckets, tables, functions, the notification mapping, log groups, the user pool
and roles. Running it again when the part is already gone is safe; it reports `not present` and passes. Check your
budget the next day.

## What you should have observed

| Observation | Where |
|---|---|
| The document answered, then authority changed while nothing told the index | A2, A3 |
| The stale copy physically remained, and still matched on label, scope and version | A4 |
| The request retrieved the stale copy and refused it on authoritative status | A5 |
| Reconciliation named the divergence and repaired it, and a second pass found nothing | A6, A7 |
| A real change entered normal delivery and failed to apply | B4 |
| It stayed pending, was retried, and kept its original clock | B5–B7 |
| Its window was breached, it escalated once, and the alarm fired | B6, B7 |
| Removing the obstruction plus one reconciliation pass restored convergence | B8–B10 |

The same observations, recorded when the implementation was validated, are in `EVIDENCE_SUMMARY.md`.

## Architecture artefacts you keep

`ARCHITECTURE_ARTEFACTS.md` has the four-state card, the two-lane diagram, the watermark definition, the escalation
contract, and a template for your own architecture note. `ARCHITECTURE_REVIEW_QUESTIONS.md` has questions to test
yourself with.

## Troubleshooting

| Symptom | Meaning and fix |
|---|---|
| `REFUSED: No lab deployment is running` | Start the part first with `lab-up`. |
| `REFUSED: This step belongs to Part A/B` | You ran a command meant for the other deployment. The message explains why it needs its own. |
| `REFUSED: another deployment is still running` | Only one part runs at a time. Run the `lab-down` it names. |
| `REFUSED: D-02 is already WITHDRAWN` / `D-04 is already CONFIDENTIAL` | You have already made that change. Re-run `lab-up` for that part: it reloads the records and rebuilds the index, so you start again. In Part B the alarm keeps its last hour, so for a completely fresh Part B run `lab-down delivery-on` and then `lab-up delivery-on`; `lab-up` warns you when this applies. |
| `AWS REQUEST FAILED: …` | A network or AWS error, often a laptop that slept mid-command (`Signature expired`). Every lab command is safe to repeat. |
| Every question is refused, and `lab-inspect` looks fine | The assistant refuses when no reconciliation pass has completed in the last hour, because it cannot prove completeness. That is the architecture working. Run `lab-reconcile`. |
| B4 says the application was `APPLIED` | You skipped `lab-obstruct`. Re-run `lab-up delivery-on` and start Part B again. |
| B7 alarm still `OK` | CloudWatch evaluates the metric about once a minute. `--wait-for-alarm` waits up to five minutes. |
| The alarm is still `ALARM` after B10 | It takes the maximum over a one-hour period, so it returns to `OK` by itself after that period. It does not latch. |
| `AccessDenied` rather than "not found" in B4 | The change function may read records but may not list the bucket, so S3 will not reveal whether an object exists. |
| Answers contain `Marker CANARY-…` | Synthetic documents carry markers so that any leak of restricted text can be detected. They are expected. |
| `lab-down … INCOMPLETE` | AWS was still deleting something. Run the same command again. |

## Expected final state

- No stack named `tla-s01e03-lab-off` or `tla-s01e03-lab-on`, and nothing else with those names.
- Your budget shows a few cents to tens of cents a day later.

## Going further (optional)

- `--verbose` on `lab-ask`, `lab-inspect` and `lab-reconcile` prints the full underlying records.
- After A6, ask A2's question again. D-02 is no longer retrieved at all. What comes back depends on the other
  documents and on the model, so it varies between runs.
- `05-implementation/README.md` explains where each responsibility lives in the code.
- `05-implementation/IMPLEMENTATION_CONTROLS.md` maps CTL-030 and the other controls to their code and permissions.

---

*Educational implementation. This is not a production system, a benchmark, or a security or compliance claim.*
