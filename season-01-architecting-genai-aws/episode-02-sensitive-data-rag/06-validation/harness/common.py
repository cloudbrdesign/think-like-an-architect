"""Paths, import setup and evidence redaction shared by the harness."""
import os
import re
import sys
from datetime import datetime, timezone

VALIDATION = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EPISODE = os.path.dirname(VALIDATION)
IMPLEMENTATION = os.path.join(EPISODE, "05-implementation")
APP = os.path.join(IMPLEMENTATION, "app")
SCRIPTS = os.path.join(IMPLEMENTATION, "scripts")
RESULTS = os.path.join(VALIDATION, "results")
for path in (APP, SCRIPTS):
    if path not in sys.path:
        sys.path.insert(0, path)

import tla_ops  # noqa: E402,F401  (deployment names, configuration and session)

ACCOUNT_ID = re.compile(r"(?<!\d)\d{12}(?!\d)")
JWT = re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}")
LOCAL_PATH = re.compile(r"(?:/Users|/home|/private|/Library|/var/folders|/opt|/usr)/[^\s\"'<>]*")


def _local(match):
    return "<local>/" + "/".join(p for p in match.group(0).split("/")[-2:] if p)


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def redact(value):
    """Evidence never carries account identifiers or tokens."""
    if isinstance(value, dict):
        return {k: redact(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact(v) for v in value]
    if isinstance(value, str):
        return LOCAL_PATH.sub(_local, JWT.sub("<token>", ACCOUNT_ID.sub("<account>", value)))
    return value
