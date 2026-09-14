"""Paths, configuration and redaction shared by the harness."""
import json
import os
import re
import sys
from datetime import datetime, timezone

HARNESS = os.path.dirname(os.path.abspath(__file__))
VALIDATION = os.path.dirname(HARNESS)
EPISODE = os.path.dirname(VALIDATION)
IMPLEMENTATION = os.path.join(EPISODE, "05-implementation")
FIXTURES = os.path.join(VALIDATION, "fixtures")
RESULTS = os.path.join(VALIDATION, "results")
TESTS = os.path.join(VALIDATION, "tests")

for path in (os.path.join(IMPLEMENTATION, "scripts"), os.path.join(IMPLEMENTATION, "app")):
    if path not in sys.path:
        sys.path.insert(0, path)

import tla_ops  # noqa: E402  (configuration, names and tags are shared with the deployment scripts)

# A UUID is kept whole (its final group can be 12 digits); any other standalone 12-digit run is treated as an account.
_ACCOUNT = re.compile(r"(?P<uuid>[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})"
                      r"|(?<![0-9])[0-9]{12}(?![0-9])")


class GuardRefused(Exception):
    """The harness refuses to run against this target (exit code 3)."""


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def redact(value):
    """Replace 12-digit account numbers everywhere (including inside ARNs). Tokens and passwords are never captured."""
    if isinstance(value, str):
        return _ACCOUNT.sub(lambda m: m.group("uuid") or "<account>", value)
    if isinstance(value, dict):
        return {redact(k): redact(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact(v) for v in value]
    return value


def load_fixtures():
    return json.load(open(os.path.join(FIXTURES, "tenants.json"), encoding="utf-8"))


def fixture_text(relative):
    return open(os.path.join(FIXTURES, relative), encoding="utf-8").read()
