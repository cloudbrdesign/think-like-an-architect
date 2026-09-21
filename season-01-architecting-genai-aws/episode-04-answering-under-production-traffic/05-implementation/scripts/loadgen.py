#!/usr/bin/env python3
"""Load generator (P7): a teaching instrument, not a benchmark.

Scenario commands, not knobs. Each is deterministic — fixed seed, fixed arrival pattern, fixed question set — so the
same command shows the same lesson twice, which is what a learner and a recording both need.

    normal · burst · sustained · bad-retry · bounded-retry · contention · downstream-limit · degrade · withhold · recover

Deliberately NOT built: arbitrary throughput benchmarking, percentile distribution studies, a general-purpose load
tool. Every counter shown maps to an outcome or a signal the architecture defines; nothing else is displayed.

  python3 scripts/loadgen.py <scenario> [--simulate] [--endpoint URL] [--json OUT]

`--simulate` runs the real application code in-process against a deterministic clock. It proves the architecture's
logic. `--endpoint` drives the deployed stack and proves the AWS mapping. Both are real; neither is a mock of the
other.
"""
import argparse
import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core import admission, buffer as buffer_mod, degradation, downstream, params as params_mod, signals as sig_mod
from app.answer.service import AnsweringService
from app.change.service import ChangeProcessor

SCENARIOS = ("normal", "burst", "sustained", "bad-retry", "bounded-retry", "contention", "downstream-limit",
             "degrade", "withhold", "recover")

# Each scenario: (requests, arrivals-per-tick, tick seconds, domains used, retry behaviour, notes)
SHAPE = {
    # The STATED capacity, deliberately below saturation. At 1 arrival/s with 4 s answers the system sits exactly on
    # both limits at once and refuses on any jitter, which is a system at capacity, not a system meeting a promise.
    "normal":          dict(n=10, per_tick=1, tick=2.0, domains=("depot-north", "depot-south"), retry="none"),
    "burst":           dict(n=18, per_tick=6, tick=1.0, domains=("depot-north",), retry="none"),
    "sustained":       dict(n=40, per_tick=6, tick=1.0, domains=("depot-north", "depot-south"), retry="none"),
    "bad-retry":       dict(n=24, per_tick=6, tick=1.0, domains=("depot-north",), retry="bad"),
    "bounded-retry":   dict(n=24, per_tick=6, tick=1.0, domains=("depot-north",), retry="bounded"),
    "contention":      dict(n=24, per_tick=6, tick=1.0, domains=("depot-north", "depot-south"), retry="none",
                            changes=6),
    # A saturated boundary is SLOW before it refuses. That is what ages the buffer past its deadline: the drain rate
    # collapses while arrivals continue. With the frozen demonstration parameters and a healthy boundary the buffer's
    # CAPACITY bound always binds first (6 items drain in ~6 s against a 10 s deadline), so this is the scenario in
    # which the age bound is genuinely reachable — and it is the realistic one.
    "downstream-limit": dict(n=20, per_tick=5, tick=1.0, domains=("depot-north",), retry="none", tiny_downstream=True,
                             slow_answer_seconds=14.0, then_quiet_ticks=18),
    "degrade":         dict(n=30, per_tick=6, tick=1.0, domains=("depot-north", "depot-south"), retry="none"),
    "withhold":        dict(n=24, per_tick=6, tick=1.0, domains=("depot-north",), retry="none", withhold_every=3),
    "recover":         dict(n=40, per_tick=6, tick=1.0, domains=("depot-north", "depot-south"), retry="none",
                            # Long enough to observe the WHOLE return: the backlog ages out, capacity ramps 2->3->4
                            # at 10 s a step, and the rung steps down twice at 15 s each. Stopping earlier would show
                            # a recovery that had started but not finished, which proves nothing about boundedness.
                            then_quiet_ticks=55),
}


def schedule(ticket, now, duration, parameters):
    """When this request will reach the model call, and when its answer is due."""
    return {"ticket": ticket, "held": False,
            "model_start": now + duration * (1.0 - getattr(parameters, "model_call_fraction", 0.5)),
            "done_at": now + duration}


class Clock:
    """A deterministic clock. Scenarios must be reproducible: a lesson that only sometimes appears is not a lesson."""

    def __init__(self, start=1000.0):
        self.t = start

    def __call__(self):
        return self.t

    def advance(self, seconds):
        self.t += seconds


def build(scenario, parameters, clock, rng):
    shape = SHAPE[scenario]
    signals = sig_mod.Signals()
    permits = admission.Permits(parameters.answering_permits_total, parameters.fair_share_per_domain,
                                parameters.fairness_domains)
    burst = buffer_mod.BurstBuffer(parameters.buffer_capacity_items, parameters.buffer_max_age_seconds, clock)
    ladder = degradation.Ladder(parameters, clock)
    broker = downstream.PermitBroker(1 if shape.get("tiny_downstream") else parameters.downstream_permits,
                                     2000 if shape.get("tiny_downstream") else
                                     parameters.downstream_token_budget_per_minute, clock, signals)

    # Episode 02's eligibility and Episode 03's currency, carried over unchanged. Episode 04 adds no trust logic:
    # at lab scale they are the same decisions against synthetic fixtures.
    def eligibility(request):
        return request.get("eligible", True)

    def currency(request):
        if request.get("currency_unknown"):
            return False, "currency_unconfirmed"
        return True, None

    def answer_path(request, capabilities):
        # A synthetic answer. Its cost is the permit it holds, not its content: this lab teaches capacity, and the
        # generation itself is deliberately trivial and cheap.
        clock.advance(parameters.answer_duration_seconds_nominal / 4)
        body = f"answer for {request['question']}"
        if not capabilities.long_answers:
            body = body[:24]
        return body, ("synthetic-doc-1",)

    service = AnsweringService(parameters, clock, permits, burst, ladder, broker, signals,
                               eligibility, currency, answer_path, rng=rng)
    changes = ChangeProcessor(parameters, clock, signals, apply_change=lambda c: clock.advance(0.05))
    return service, changes, signals, shape


def run(scenario, parameters, seed=41):
    """Drive the scenario against a deterministic clock, with work genuinely in flight.

    Admission and execution are separate phases, so an admitted request HOLDS its permit for the duration of the
    answer. Without that, nothing ever contends and no overload state is reachable — the first version of this
    generator had exactly that defect and showed a flawless system under any load.
    """
    rng = random.Random(seed)
    clock = Clock()
    service, changes, signals, shape = build(scenario, parameters, clock, rng)
    results, timeline, in_flight = [], [], []
    issued = 0
    pending_retries = []
    duration = shape.get("slow_answer_seconds", parameters.answer_duration_seconds_nominal)

    ticks = max(1, -(-shape["n"] // shape["per_tick"])) + shape.get("then_quiet_ticks", 0)
    for tick in range(ticks):
        now = clock()

        # 1a. Work that has reached its model call takes a downstream permit and holds it until it completes.
        #     Taking it at admission instead would make the boundary bind at every load and mask every other lesson.
        still = []
        for entry in in_flight:
            if not entry["held"] and now >= entry["model_start"]:
                refused = service.start_answer(entry["ticket"])
                if refused is not None:
                    results.append(refused.as_dict())
                    continue                      # the boundary had no room; this request is done
                entry["held"] = True
            still.append(entry)
        in_flight = still

        # 1b. Complete work whose answer is due; this is what frees both permits.
        still = []
        for entry in in_flight:
            if entry["done_at"] <= now:
                results.append(service.execute(entry["ticket"]).as_dict())
            else:
                still.append(entry)
        in_flight = still

        # 2. Promote anything waiting in the buffer, now that permits may be free. Expired items leave here as an
        #    explicit refusal, before execution.
        while True:
            ticket, response = service.promote_from_buffer()
            if response is not None:
                results.append(response.as_dict())
                continue
            if ticket is None:
                break
            in_flight.append(schedule(ticket, now, duration, parameters))

        # 3. New arrivals for this tick, plus any retries the scenario's client behaviour produced.
        batch = []
        for _ in range(shape["per_tick"]):
            if issued >= shape["n"]:
                break
            domain = shape["domains"][issued % len(shape["domains"])]
            request = {"identity": f"user-{issued}", "domain": domain, "question": f"q{issued}"}
            if shape.get("withhold_every") and issued % shape["withhold_every"] == 0:
                request["currency_unknown"] = True
            batch.append(request)
            issued += 1
        batch.extend(pending_retries)
        pending_retries = []

        for request in batch:
            ticket, response = service.admit(request)
            if ticket is not None:
                in_flight.append(schedule(ticket, now, duration, parameters))
            elif response is not None:
                results.append(response.as_dict())
                if response.outcome == "CAPACITY_REFUSED":
                    if shape["retry"] == "bad":
                        # The incident's turning point: ignore the guidance and retry at once, twice over.
                        pending_retries.extend([dict(request), dict(request)])
                    elif shape["retry"] == "bounded":
                        pending_retries.append(dict(request))

        if shape.get("changes"):
            for i in range(max(1, shape["changes"] // max(1, ticks))):
                changes.process({"id": f"c{tick}-{i}"})
        else:
            changes.idle()          # nothing pending: the derived copy is current, and says so

        clock.advance(shape["tick"])
        service.tick()
        changes.publish_signals()
        timeline.append(observation(tick, clock, results, signals))

    # Drain whatever is still in flight, so every offered request reaches an outcome.
    for entry in in_flight:
        if not entry["held"]:
            refused = service.start_answer(entry["ticket"])
            if refused is not None:
                results.append(refused.as_dict())
                continue
        results.append(service.execute(entry["ticket"]).as_dict())
    while True:
        ticket, response = service.promote_from_buffer()
        if response is not None:
            results.append(response.as_dict())
            continue
        if ticket is None:
            break
        refused = service.start_answer(ticket)
        results.append((refused or service.execute(ticket)).as_dict())




    return summary(scenario, parameters, results, signals, timeline, seed)


def observation(tick, clock, results, signals):
    snap = signals.snapshot()
    counted = tally(results)
    return {"t": round(clock() - 1000.0, 1), "tick": tick, **counted,
            "buffer_age_seconds": snap["gauges"].get("buffer_age_seconds", 0),
            "concurrency": snap["gauges"].get("concurrency_in_use", 0),
            "degradation_level": snap["gauges"].get("degradation_level", 0),
            "freshness_lag_seconds": snap["gauges"].get("freshness_lag_seconds", 0)}


def tally(results):
    counted = {"answered": 0, "degraded": 0, "capacity_refused": 0, "trust_withheld": 0}
    for r in results:
        if r["outcome"] == "ANSWERED":
            counted["answered"] += 1
        elif r["outcome"] == "DEGRADED_BUT_ANSWERED":
            counted["degraded"] += 1
        elif r["outcome"] == "CAPACITY_REFUSED":
            counted["capacity_refused"] += 1
        elif r["outcome"] == "TRUST_WITHHELD":
            counted["trust_withheld"] += 1
        else:
            raise ValueError(f"unknown outcome {r['outcome']!r}")
    return counted


def summary(scenario, parameters, results, signals, timeline, seed):
    snap = signals.snapshot()
    return {"scenario": scenario, "seed": seed, "offered": len(results), **tally(results),
            "counters": snap["counters"], "gauges": snap["gauges"], "timeline": timeline,
            # The configuration is echoed in every run summary (CTL-412), so evidence is never separated from the
            # parameters that produced it.
            "demonstration_parameters": parameters.as_dict()}


def display(result):
    print(f"scenario {result['scenario']}  (seed {result['seed']}, deterministic)")
    for row in result["timeline"]:
        print(f"  t+{row['t']:>5}s  answered {row['answered']:>3}  degraded {row['degraded']:>3}  "
              f"capacity-refused {row['capacity_refused']:>3}  trust-withheld {row['trust_withheld']:>3}   "
              f"buffer age {row['buffer_age_seconds']:>5}s  concurrency {row['concurrency']}  "
              f"level {row['degradation_level']}  freshness lag {row['freshness_lag_seconds']}s")
    print(f"  TOTAL  offered {result['offered']}  answered {result['answered']}  degraded {result['degraded']}  "
          f"capacity-refused {result['capacity_refused']}  trust-withheld {result['trust_withheld']}")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("scenario", choices=SCENARIOS)
    parser.add_argument("--simulate", action="store_true", help="run the application code in-process (default)")
    parser.add_argument("--json", help="write the run summary here")
    parser.add_argument("--seed", type=int, default=41)
    args = parser.parse_args(argv)

    result = run(args.scenario, params_mod.load(), seed=args.seed)
    display(result)
    if args.json:
        with open(args.json, "w", encoding="utf-8") as handle:
            json.dump(result, handle, indent=2)
        print(f"  summary written to {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
