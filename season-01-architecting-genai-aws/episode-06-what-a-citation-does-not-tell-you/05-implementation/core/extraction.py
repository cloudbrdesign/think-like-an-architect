#!/usr/bin/env python3
"""OPTIONAL EXTENSION — falsifying a CANDIDATE architecture, not implementing the answer.

One tempting response to everything this lab shows is: stop letting the model assert instructions, and
quote the procedure instead. That is a real candidate architecture. It was NOT selected, and this module
exists only to show three ways quoting alone still fails to keep the promise.
"""
from . import corpus

PROBES = {
    "P-1 governing context lost": {
        "cites": ["D-204#4"], "framing": "",
        "what_to_notice": "Verbatim and correctly cited - and it reads as if it applies to every unit.",
    },
    "P-2 governing context carried": {
        "cites": ["D-204#3", "D-204#4"], "framing": "",
        "what_to_notice": "The same instruction, now inseparable from the condition that limits it.",
    },
    "P-3 connective framing": {
        "cites": ["D-204#1"], "framing": "For your unit, this means the terminals stay live:",
        "what_to_notice": "Every quoted word is authoritative. The sentence introducing them is not.",
    },
    "P-4 competing values": {
        "cites": ["D-204#2", "D-204#4"], "framing": "",
        "what_to_notice": "Two real torque values, one of them conditional, and nothing saying which "
                          "applies to the unit in front of you.",
    },
}

ACTIONABLE = {"D-204#1", "D-204#2", "D-204#4", "D-204#5"}   # D-204#3 states a condition, not an instruction


def render(cites, framing=""):
    quoted = " ".join(corpus.text(s) for s in cites)
    return (framing + " " + quoted).strip() if framing else quoted


def problems(cites, framing):
    found = []
    for s in cites:
        for g in corpus.governors(s):
            if g not in cites:
                found.append(f"applicability lost: {s} is limited by {g}, which was not quoted")
    if framing:
        found.append("connective framing: the answer asserts something outside the quoted text")
    actionable = [s for s in cites if s in ACTIONABLE]
    if len(actionable) > 1 and any(corpus.governors(s) for s in actionable):
        found.append("competing values: more than one instruction, at least one conditional")
    return found
