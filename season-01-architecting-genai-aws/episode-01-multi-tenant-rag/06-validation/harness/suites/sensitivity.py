"""TST-SEN-011 — the cross-tenant tests run against the SENSITIVITY deployment, where CTL-015 is removed.

Here FAIL is the expected, useful result: it shows the tests observe the retrieval layer and detect the missing control.
The verdict (sensitivity-verdict) combines baseline, variant, cleanup and bracketing runs.
"""
from harness.suites.isolation import run_negative


def run(ctx):
    if ctx.target.variant != "sensitivity":
        raise RuntimeError("the sensitivity suite runs only against the sensitivity variant")
    run_negative(ctx, suite="sensitivity")
