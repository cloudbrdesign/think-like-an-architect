"""Shared helpers for the Episode 04 suite. Deliberately thin: this is not test machinery to be tested."""
import os
import sys

IMPLEMENTATION = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if IMPLEMENTATION not in sys.path:
    sys.path.insert(0, IMPLEMENTATION)
sys.path.insert(0, os.path.join(IMPLEMENTATION, "scripts"))

from app.core import params as params_mod            # noqa: E402
import loadgen                                        # noqa: E402


def parameters():
    return params_mod.load()


def run(scenario, seed=41):
    return loadgen.run(scenario, parameters(), seed=seed)


def outcomes_of(result):
    return {k: result[k] for k in ("answered", "degraded", "capacity_refused", "trust_withheld")}
