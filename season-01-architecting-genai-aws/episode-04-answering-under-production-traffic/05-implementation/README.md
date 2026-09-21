# Episode 04 implementation — answering under production traffic

The capacity contract, built. Seven parts, each earning its place by demonstrating an accepted decision. Read
[`IMPLEMENTATION_DESIGN.md`](IMPLEMENTATION_DESIGN.md) first: this directory is that design made runnable, and where
the two differ, the deviations are listed below rather than quietly absorbed.

## What is here

| Part | Where | Decision it serves |
|---|---|---|
| **P1** Admission controller | `app/core/admission.py` | ADR-001, 002, 003, 006 |
| **P2** Age-bounded burst buffer | `app/core/buffer.py` | ADR-002 |
| **P3** Answer worker | `app/answer/service.py` | ADR-004 |
| **P4** Downstream permit broker | `app/core/downstream.py` | ADR-005 |
| **P5** Change-processing worker | `app/change/service.py` | ADR-003 |
| **P6** Signals | `app/core/signals.py` | ADR-007 |
| **P7** Load generator | `scripts/loadgen.py` | teaching instrument |
| The trust path | `app/core/trust.py` | **ADR-004 — the one that matters** |
| Degradation ladder | `app/core/degradation.py` | ADR-004 |
| Bounded recovery | `app/core/recovery.py` | ADR-008 |
| AWS mapping | `infrastructure/template.yaml` | §8 of the design |
| Demonstration parameters | `config/demonstration_parameters.json` | CTL-412 |

**The one thing to read if you read nothing else:** `app/core/trust.py`. Every answer in the system is constructed by
`serve()`, and by nothing else. The degradation rung is a parameter to the *answer* path, applied after the trust path
has already run. There is no configuration key, flag or operator action that reaches eligibility, currency or
citation — and `Capabilities` raises rather than allow one to be added. *Operators may reduce service. Operators may
not reduce trust.*

## Running it

```bash
python3 scripts/loadgen.py normal            # the promise, at the stated load
python3 scripts/loadgen.py sustained         # the buffer's capacity bound, and the ladder rising
python3 scripts/loadgen.py downstream-limit  # a slow boundary, and the AGE bound expiring work
python3 scripts/loadgen.py withhold          # TRUST_WITHHELD while saturated - never a degraded answer
python3 scripts/loadgen.py bad-retry         # then `bounded-retry`: the same burst, one contract apart
python3 scripts/loadgen.py recover           # backlog ages out, permits ramp 2->3->4, rung steps down

cd tests && python3 -m unittest discover -s .     # 27 activities: TST-401...411 and FX-1/2/3

python3 scripts/tla_ops.py preflight              # account, region, budget, leftovers, provisioned throughput
python3 scripts/tla_ops.py lab-up traffic
python3 scripts/tla_ops.py lab-down traffic       # idempotent; proves absence by an independent scan
```

Scenarios are deterministic (fixed seed, fixed arrivals, fixed questions): a lesson that only sometimes appears is not
a lesson.

## Deviations from the frozen E3 design — read these

1. **Reserved concurrency is not in force.** The design maps partitioned capacity (CTL-401, CTL-409) to Lambda
   reserved concurrency. **Whether it is available depends on your account's concurrency quota**, because AWS refuses any reservation
   that would leave the account below its required unreserved capacity. In a low-quota account no reservation
   is possible at all. Check yours with `aws lambda get-account-settings`. The partitions are enforced by the
   in-process permit counter, which CTL-401 names as the other half of the same control. `tla_ops.py` decides this
   from the live account limit and says which enforcement is in force. **The architecture is unchanged; its AWS
   enforcement layer is absent.** See the lab README for why a cloud quota is an architectural constraint rather than a footnote.

2. **The buffer's age bound is only reachable when the boundary slows.** With the frozen parameters, six items drain
   in about six seconds against a ten-second deadline, so the **capacity** bound always binds first. The age bound is
   demonstrated in `downstream-limit`, where a slow downstream collapses the drain rate — which is the realistic
   trigger, and arguably the better lesson.

3. **`model_call_fraction` was added** to the demonstration parameters. A model call is part of an answer, not the
   whole of it; without this the downstream boundary binds at every load and masks every other lesson.

4. **The `normal` scenario offers below saturation.** At one arrival per second the system sits exactly on both limits
   and refuses on any jitter. That is a system at capacity, not a system meeting a promise.

## Defects found while building, and what they showed

| Found | Why it mattered |
|---|---|
| Fair share let one depot take the whole pool | Free capacity is not available capacity: a permit idle but owed to a quiet domain must stay idle |
| Re-queuing an unpromotable item **reset its deadline** | An item whose clock restarts can never expire, which makes the age bound unenforceable |
| The degradation rung was only recomputed on arrival | A quiet system stayed stuck at the rung its last burst reached — recovery is exactly when nothing is arriving |
| The downstream reject ratio was a **lifetime** average | A boundary that rejected once read as saturated forever, so the ladder could never step down |
| The recovery ramp waited for the rung to reach NORMAL | Capacity should follow the queue; capability follows the pressure signal. Tying them together delayed capacity by two hysteresis intervals |

Every one of these was found by running the thing, and every one is a way a system stays broken after the incident
has passed.
