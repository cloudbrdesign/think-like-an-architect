"""Red-team guard probes for the operational attacks that are not API requests:
RT-15 sensitivity-stack targeting mistake · RT-16 cleanup against the wrong stack, account or region.
(The other red-team attacks are exercised by the named tests; see the E4 red-team table.)
"""
import os
import subprocess
import sys

from harness.common import IMPLEMENTATION, GuardRefused
from harness.target import Target

SUITE = "redteam"


def _ops(args, **env):
    environment = {**os.environ, **env}
    environment.pop("TLA_SENSITIVITY_RUN", None)
    result = subprocess.run([sys.executable, "scripts/tla_ops.py", *args], cwd=IMPLEMENTATION, capture_output=True,
                            text=True, env=environment, timeout=300)
    return result.returncode, (result.stdout + result.stderr).strip().splitlines()[-1:]


def run(ctx):
    normal_stack = ctx.target.stack_name
    probes, problems = {}, []
    for label, variant, stack in (("sensitivity suite aimed at the normal stack", "sensitivity", normal_stack),
                                  ("normal suite aimed at a sensitivity stack name", "normal", "tla-s01e01-sensitivity")):
        try:
            Target(variant, stack_override=stack)
            probes[label] = "ACCEPTED"
            problems.append(f"{label}: guard did not refuse")
        except GuardRefused as refusal:
            probes[label] = f"REFUSED: {refusal}"
    code, tail = _ops(["deploy", "sensitivity"])
    probes["deploy sensitivity variant outside sensitivity-run.sh"] = {"exit": code, "output": tail}
    if code == 0:
        problems.append("sensitivity deploy allowed outside the sensitivity run")
    ctx.run.record("RT-15", SUITE, ["SEC-004"], ["CTL-015"], "red-team",
                   "Suites and deployment refuse to target the wrong variant", "FAIL" if problems else "PASS",
                   "; ".join(problems) or "variant guards refused every wrong-target attempt", probes)
    probes, problems = {}, []
    code, tail = _ops(["cleanup", "--variant", "normal"], TLA_EXPECTED_ACCOUNT="000000000000")
    probes["cleanup with a different expected account"] = {"exit": code, "output": tail}
    if code == 0 or "REFUSED" not in " ".join(tail):
        problems.append("cleanup ran against an unexpected account")
    still_there = ctx.target.client("cloudformation").describe_stacks(StackName=normal_stack)["Stacks"][0]["StackStatus"]
    probes["normal stack after the refused cleanup"] = still_there
    code, tail = _ops(["outputs", "sensitivity"])
    probes["outputs for a stack that does not exist (no side effects)"] = {"exit": code}
    ctx.run.record("RT-16", SUITE, ["OPS-004"], [], "red-team",
                   "Cleanup refuses an unexpected account and never touches a stack it was not asked to remove",
                   "FAIL" if problems else "PASS", "; ".join(problems) or f"cleanup refused the wrong account; normal stack still {still_there}",
                   probes)
