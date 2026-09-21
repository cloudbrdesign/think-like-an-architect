"""Demonstration parameters, loaded from one file (CTL-412).

Every number that shapes behaviour lives in `config/demonstration_parameters.json` and is echoed in every run summary.
They are DEMONSTRATION values, not production recommendations: they are small enough that a learner reaches every
state in minutes, at negligible cost.
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
IMPLEMENTATION = os.path.dirname(os.path.dirname(HERE))
DEFAULT_PATH = os.path.join(IMPLEMENTATION, "config", "demonstration_parameters.json")


class Parameters:
    def __init__(self, values):
        self._values = {k: v for k, v in values.items() if not k.startswith("_")}
        for key, value in self._values.items():
            setattr(self, key, value)

    def as_dict(self):
        return dict(self._values)


def load(path=None):
    """Read the parameters. The environment may override the file, because the lab functions receive them as
    configuration rather than carrying a copy of the file into the deployment package."""
    with open(path or os.environ.get("TLA_PARAMETERS_PATH") or DEFAULT_PATH, encoding="utf-8") as handle:
        values = json.load(handle)
    override = os.environ.get("TLA_PARAMETERS_JSON")
    if override:
        values.update(json.loads(override))
    return Parameters(values)
