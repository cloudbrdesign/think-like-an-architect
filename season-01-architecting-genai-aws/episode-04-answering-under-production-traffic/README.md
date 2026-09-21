# Answering under production traffic

**Think Like an Architect — Season 1, Episode 04.**

A knowledge assistant that works perfectly in testing falls over on its first busy Monday. Not because the code is
wrong, but because nobody decided what it should do when there is more work than capacity.

This lab builds the decision, not the fix.

---

## Start here, not with the commands

**Read [`CONCEPTS.md`](CONCEPTS.md) first.** It explains request rate, concurrency, back-pressure, queue age, load
shedding, retry amplification, jitter, quotas, throttling, degradation, fairness and recovery in plain English, and
names the misconception each one replaces.

The lab is much less useful if you meet these terms for the first time inside a command. Ten minutes there saves the
whole exercise.

Then read [`ARCHITECTURE.md`](ARCHITECTURE.md): the problem, the decision, and what was actually built.

## The question this episode answers

> When more work arrives than you can serve, **what should the system do** — and who decides?

The wrong answers are familiar. Slow down for everybody. Queue everything and hope. Scale up and discover the limit was
never yours. Retry until the retries are the outage.

The answer this episode argues for:

> **Finite capacity requires an explicit service contract.**
> Decide in advance what you will refuse, who gets refused first, what you will drop to stay useful — and what you will
> never drop, no matter how bad it gets.

And the invariant that makes it safe:

> **Degrade capability, not trust.** Operators may reduce service. Operators may not reduce trust.

## What you will see

You run scenarios against a small deployment and watch it behave. Each one is deterministic: the same command shows the
same lesson twice.

| # | You will observe | Scenario |
|---|---|---|
| 1 | Rate and concurrency are different things | `normal` |
| 2 | Admission control: some work admitted, some refused, immediately and honestly | `burst` |
| 3 | A buffer bounded by **capacity and age** — not an unbounded queue | `sustained` |
| 4 | Explicit load shedding, with the caller told the truth | `sustained` |
| 5 | **Retry amplification**: the same burst becomes an outage | `bad-retry` |
| 6 | Bounded retries with jitter keep it survivable | `bounded-retry` |
| 7 | Fair capacity: one flooding tenant cannot starve a quiet one | `burst`, `contention` |
| 8 | Downstream quota pressure — the limit that is not yours | `downstream-limit` |
| 9 | Graceful degradation, by ordered rungs | `degrade` |
| 10 | **Trust checks that do not degrade**, at any rung | `withhold` |
| 11 | `CAPACITY_REFUSED` and `TRUST_WITHHELD`, never merged | `withhold` |
| 12 | A second workload keeping its floor while freshness visibly slips | `contention` |
| 13 | Saturation signals that reach an operator before a user complains | `sustained` |
| 14 | Bounded recovery: backlog ages out, capacity returns in stages | `recover` |
| 15 | **A cloud quota turning out to be an architectural constraint** | quota discovery, below |

---

## Part 1 — Run it locally first (no AWS, no cost)

Everything architectural in this lab is visible without deploying anything. Start here.

```bash
cd 05-implementation
python3 scripts/loadgen.py normal
```

All ten requests answered, nothing refused. That is the promise being kept at the stated load.

Now break it:

```bash
python3 scripts/loadgen.py burst
```

Three visibly different fates in one run: some answered, some degraded, some refused. Look at the `buffer age` column —
that is the signal that leads.

```bash
python3 scripts/loadgen.py bad-retry
python3 scripts/loadgen.py bounded-retry
```

**Compare the `offered` totals.** Same burst, one retry contract apart. This is the single most important pair of runs
in the lab.

```bash
python3 scripts/loadgen.py sustained          # the buffer's capacity bound, and the ladder rising
python3 scripts/loadgen.py downstream-limit   # a slow boundary, and work expiring past its deadline
python3 scripts/loadgen.py contention         # a second workload keeping its floor
python3 scripts/loadgen.py degrade            # ordered rungs
python3 scripts/loadgen.py withhold           # TRUST_WITHHELD while saturated
python3 scripts/loadgen.py recover            # backlog ages out, permits ramp, rung steps down
```

Each accepts `--json out.json` to write a run summary, and `--seed N` if you want to vary the arrival pattern.

### The run that matters most

```bash
python3 scripts/loadgen.py withhold --json withhold.json
```

The system is saturated. It is refusing work. And some requests come back **`TRUST_WITHHELD`** — not refused for
capacity, not answered with a caveat, but declined because they could not be answered correctly.

Then look at the counters in `withhold.json`. `capacity_refused` and `trust_withheld` are separate numbers, and they
stay separate all the way out to the caller's payload: a capacity refusal carries `retry_after_seconds`, a trust
withhold **never does**. Retrying harder will not help, so the system does not imply that it might.

**That is what "degrade capability, not trust" means in code.** Under pressure, the system gave up optional
capability — and gave up nothing else.

## Part 2 — The tests are the argument

```bash
cd 05-implementation/tests
python3 -m unittest discover -s .
```

27 activities. They run the real application code against a deterministic clock, so each one is a claim about the
architecture rather than a claim about a test harness.

Three of them are **failure experiments** — deliberately broken variants that must fail:

| | Breaks | Proves |
|---|---|---|
| **FX-1** | Admission control and the age bound: everything queued | A queue relocates overload. **Age** is the property that matters |
| **FX-2** | The retry contract | Offered load multiplies; a survivable burst becomes an outage |
| **FX-3** | Makes a degradation rung serve an unverified result | **The trust invariant must be structural, not documented** |

FX-3 is the important one. It adds a `skip_currency_check` switch to the capability set — exactly what somebody adds at
three in the morning to make the graphs look better. The code **raises** rather than allow it. Read
`05-implementation/app/core/trust.py` and see why: `serve()` is the only function in the system that can construct an
answer, and the degradation rung is a parameter to the *answer* path, applied after the trust path has already run.
There is no configuration key that reaches eligibility or currency, and a capability set that grows one is rejected.

## Part 3 — Deploy it (optional, small cost)

The local runs prove the architecture. Deploying proves the **AWS mapping**: that reserved concurrency really is the
partition, that a message deadline really is checked before execution, and that the four outcomes really do stay
separate in metrics and alarms.

### Before anything: discover your own quotas

**Do not assume the numbers in this lab are yours.** Quotas differ by account, by age, and by region.

```bash
aws lambda get-account-settings --region <your-region> \
  --query 'AccountLimit.{Concurrent:ConcurrentExecutions,Unreserved:UnreservedConcurrentExecutions}'
```

This single command is the fifteenth lesson in the list above, and it is worth pausing on.

**Reserved concurrency is the mechanism this architecture proposed** for partitioning capacity: it sets both a maximum
and a guaranteed minimum for a function, so one workload cannot consume what another needs. But AWS will refuse any
reservation that would leave the account below its required unreserved capacity. **In a low-quota account, reserved
concurrency is simply not available** — you cannot reserve anything at all.

That is not a footnote. It is the lesson:

| | |
|---|---|
| **Architecture intent** | Workloads require bounded, partitioned capacity with protected floors |
| **Cloud implementation mechanism** | Reserved concurrency was the proposed enforcement — and the account quota can make it unavailable |
| **As-built control** | Application-level permits enforce the required behaviour instead |

The architecture did not change. Its **enforcement layer** did. The deployment tooling detects this from your live
account and tells you which enforcement is in force:

```
partitions  enforced by AWS reserved concurrency (5 of 1000, leaving 995 unreserved)
```
or
```
partitions  enforced IN-PROCESS: account concurrency limit is N, and reserving 5 would
            leave fewer than 10 unreserved, which AWS refuses
```

**These are not equivalent in every operational property.** Application permits bound concurrency *within* a process
and across the instances you run; reserved concurrency is enforced by the platform itself, survives your code being
wrong, and guarantees a floor no other function can take. If you have the quota, use it. If you do not, you now know
exactly what you are missing and why — which is a better position than discovering it during an incident.

**Cloud quotas are architectural constraints.** They belong in the design, not in the troubleshooting guide.

### Deploy

```bash
cd 05-implementation
cp config/learner.env.example config/learner.env    # then edit it
python3 scripts/tla_ops.py preflight
python3 scripts/tla_ops.py lab-up traffic
```

`learner.env` needs **your** account id and region. `preflight` refuses to create anything unless the account matches
what you declared and a budget exists — both deliberate.

Then drive it and watch:

```bash
python3 scripts/tla_ops.py inspect traffic
```

Send work through the buffer (substitute your own queue URL from the `lab-up` output), including one message whose
`enqueued_at` is already older than the age bound, and watch it come back `CAPACITY_REFUSED` **before** it is ever
executed. Then look at the alarms: the capacity alarm and the trust alarm fire **independently**, from different
metrics. Four alerts, never merged.

### Clean up — not optional

```bash
python3 scripts/tla_ops.py lab-down traffic
```

It deletes the stack, removes the artifacts bucket, and then **proves absence** with an independent scan of each owning
service rather than trusting a tag index. Run it twice; the second run is a clean no-op. That is what a cleanup
assertion should look like.

---

## What this costs

At the scale in this lab, essentially nothing — but **verify against current pricing for your own region**, and set a
budget with alerts before you create anything.

| Component | At lab scale |
|---|---|
| Lambda | Tens of invocations; comfortably inside the monthly free tier |
| SQS | A few thousand requests at most; the free tier is 1,000,000/month |
| CloudWatch alarms | 4 alarms; the first 10 are free |
| CloudWatch custom metrics | ~5 metrics, prorated hourly, for the time the lab exists |
| CloudWatch API requests | Inside the free tier |

The lab's answer path is **synthetic** and calls no model, so there is no token cost. If you extend it to call a real
model, that becomes your dominant cost and you should price it before you run it.

**Local runs (Part 1 and Part 2) cost nothing at all.** They are also where most of the learning is.

## Known limitations

- **The answer path is synthetic.** This lab teaches capacity behaviour, not retrieval or generation quality. The cost
  of an answer here is the permit it holds, not the content it produces.
- **The local runs use a deterministic clock**, not wall-clock concurrency. That is deliberate: a lesson that only
  sometimes appears is not a lesson. It means timings are reproducible, not that they are real-world measurements.
- **The demonstration parameters are tiny by design** (4 permits, a 6-item buffer, a 10-second deadline) so every state
  is reachable in minutes. **They are not production recommendations.** They live in one file,
  `05-implementation/config/demonstration_parameters.json` — change one value and watch the behaviour move.
- **With the default parameters the buffer's capacity bound binds before its age bound** under steady drain. The age
  bound is reached in `downstream-limit`, where a slow boundary collapses the drain rate. That is the realistic
  trigger, and arguably the better lesson.
- **This is not a benchmark.** There is no throughput measurement, no percentile study, and no load-testing tool here.
  The generator is a teaching instrument.
- **Trust logic is inherited, not rebuilt.** Eligibility comes from Episode 02 and currency from Episode 03. Episode 04
  adds capacity behaviour *around* those invariants; it does not redesign them.

## Repository layout

```
CONCEPTS.md              read first - the vocabulary, in plain English
ARCHITECTURE.md          the problem, the decision, and what was built
01-business-context/     the situation and the teaching prerequisites
02-requirements/         requirements, assumptions and constraints
03-architecture/         target architecture and threat model
04-decisions/            the decision questions, the options, and ADR-001...008
05-implementation/       the running system, its tests and its deployment
06-validation/           what was tested, and why those tests and not others
```

Read `04-decisions/` if you only read one directory. The ADRs are where the architecture is actually decided, and each
one records what was given up.

---

*Part of [Think Like an Architect](https://github.com/cloudbrdesign) — architecture engagements worked end to end, with
the decisions and the evidence left in.*
