# Educational implementation — keeping the knowledge base current

The Episode 03 implementation of the approved architecture: **convergence-aware derived retrieval + authoritative
request-time status confirmation + generation-based repair and rebuild.** It is built on Episode 02's assistant, which
is inherited unchanged and runs as a regression.

Synthetic data only. A sandbox account only. Deploy, validate and clean up in one session.

## The three responsibilities, kept apart

| Responsibility | Where it lives | What it may never do |
|---|---|---|
| **Protect the request** | `core/record_state.py`, `core/convergence.py`, `core/verification.py`, `query/handler.py` | Trust the index. Currency comes from the authoritative record, read per request. |
| **Prove convergence** | `change/notifier.py`, `change/reconciler.py`, `core/freshness.py` | Treat delivery as proof. Only a completed reconciliation pass may advance a watermark. |
| **Rebuild when necessary** | `change/applier.py`, `core/generations.py`, `change/rebuild.py` | Move a document backwards, or serve half a generation. |

## Reading order

1. `IMPLEMENTATION_DESIGN.md` — what is built, which service was chosen for each responsibility and why, and the
   as-built decisions (including the one with observable request-path behaviour).
2. `IMPLEMENTATION_CONTROLS.md` — CTL-030 … CTL-036: what each control does, the code that implements it, the
   permission that expresses it, and the test that fails if it is removed.
3. `infrastructure/template.yaml` — read the IAM roles first. They answer "who may write derived state?", "who may
   advance a watermark?" and "who may search each tier?" better than any diagram.
4. `app/core/` — every rule that decides whether a document may be answered as current, as plain Python with unit
   tests and no AWS.
5. `../06-validation/` — the learner lab tooling; `../README.md` walks through it.

## Running it

```
python3 -m unittest discover -s tests -t tests          # local component tests, no AWS, no credentials
cp config/learner.env.example config/learner.env        # then fill in your account
python3 scripts/tla_ops.py preflight                    # models, region, budget, leftovers from a previous run
python3 scripts/tla_ops.py lab-up delivery-off           # then follow ../README.md, Part A and Part B
python3 scripts/tla_ops.py lab-down delivery-off
python3 scripts/tla_ops.py lab-down delivery-on
```

`COST_AND_CLEANUP.md` has the cost model and the full cleanup flow. Read it before deploying.

## Two things worth knowing before you read the code

- **A deployment that has never completed a reconciliation pass answers nothing.** That is deliberate: the system
  cannot prove completeness, so it withholds rather than answering on an unprovable claim. Loading fixtures runs a
  pass; so does `python3 -m harness lab-reconcile`.
- **A document whose classification record is invalid is recorded as `QUARANTINED`, not as pending.** "Nothing may be
  indexed from this record" is a decision, not an unfinished job. Four documents in the corpus are deliberately like
  this.

## What this is not

Not a production system, not a benchmark, and not a security or compliance claim. Measurements taken here are
educational observations at educational scale — about a dozen documents, never the fictional client's 180,000.
