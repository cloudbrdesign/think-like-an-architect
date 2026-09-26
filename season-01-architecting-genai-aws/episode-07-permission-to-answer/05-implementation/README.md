# Episode 07 lab — how to fail over without silently changing the promise

## Prerequisites

Python 3.10+ and nothing else. **No AWS account. No cloud resources. No API key. No model call. No
network access. No cost. Nothing to clean up.**

## How to run it

```
python3 lab_failover.py --step 1      # the authority, and what "in force" means
python3 lab_failover.py --step 2      # the failover path that inherits permission
python3 lab_failover.py --step 3      # the decision, and the four conditions that must stay distinct
python3 lab_failover.py --step 4      # reduce capability, not trust
python3 lab_failover.py --step 5      # relocation is not currency
python3 lab_failover.py --step 6      # the number this lab refuses to invent

python3 lab_failover.py --attack 1    # delete the mapping
python3 lab_failover.py --attack 2    # the records owner waives an obligation by editing the mapping
python3 lab_failover.py --attack 3    # fetch the mapping across the route that failed
python3 lab_failover.py --attack 4    # sign and cache the dependent copy

python3 lab_failover.py --all         # everything, in order
python3 qa_lab.py                     # the lab's own checks, if you want to see them pass
```

**Read step 2 before step 3.** The point is not that a refusal is possible; it is that the answer in
step 2 looks completely normal.

## The four attacks

Each one is an attempt to make the system serve when it should not. All four must **fail closed** — and
the interesting one is attack 2, which is not a technical attack at all: the records owner edits the
mapping to say that an actionable instruction no longer needs current confirmation. It fails because
**owning the mapping's content is not the same as holding the authority to waive a safety obligation.**
Those are two different people in the organisation, and the code will not let one stand in for the other.

## What this lab does NOT establish

- **It never decides whether an answer is carried by the section it cites.** `o6_grounding` is reported
  as `NOT_DECIDABLE` and never computed. Episode 06 could not establish that control and this lab does
  not pretend to have one. **You** adjudicate it.
- **It sets no staleness threshold**, and it contains no seconds, minutes, percentages, SLOs or budgets.
  Ticks are an ordering, not a duration. Whether any staleness is tolerable for an actionable
  instruction is a policy ruling that belongs to Safety & Compliance.
- **It says nothing about how people behave.** Whether a technician told *"this may have changed"* acts
  differently is untested here, and no output claims otherwise. No simulated technician exists.
- **It says nothing about organisations** — not whether refusal would be accepted, nor how often.
- **It is a constructed teaching case.** It establishes no frequency, probability, production behaviour,
  real-model behaviour, general LLM or RAG property, and nothing about any cloud provider or region.
- **No architecture topology is supplied.** The decision is an invariant and a set of composable
  responsibilities, not a deployment diagram, and the absence of a diagram is part of the lesson.

## Episode 04's contract is unchanged

The caller sees the four outcomes Episode 04 established — `ANSWERED`, `DEGRADED_BUT_ANSWERED`,
`CAPACITY_REFUSED`, `TRUST_WITHHELD` — and **no fifth one is introduced here.** What the record carries
underneath is `MUST_NOT_ANSWER` versus `CANNOT_ESTABLISH_PERMISSION_TO_ANSWER` versus
`CANNOT_DETERMINE_OBLIGATIONS`. *We may not* and *we cannot tell* are different facts, and an incident
review that cannot separate them cannot answer a regulator.
