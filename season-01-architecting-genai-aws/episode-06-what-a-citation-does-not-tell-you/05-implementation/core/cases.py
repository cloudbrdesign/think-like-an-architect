#!/usr/bin/env python3
"""The answers the learner runs the controls against.

Each case records what the procedure ACTUALLY carries — not because anyone judged it, but because the
procedure and the answer were both written here. That is 'construction authority', and it is the only
kind of authority this lab has. It is enough to show that a state is REACHABLE. It is not enough to say
how often anything happens.
"""
PRINCIPAL = "tech-4417"
RETRIEVED = ["D-204#1", "D-204#2", "D-204#3", "D-204#4", "D-204#5"]

CASES = {
    "normal": {
        "question": "What torque for the terminal bolts?",
        "answer": "Torque the terminal bolts to 40 Nm.",
        "claim": "Torque the terminal bolts to 40 Nm.",
        "cites": ["D-204#2"],
        "expected": "SUPPORTED",
        "note": "The cited section carries exactly this instruction.",
    },
    "quiet": {
        "question": "What torque for the terminal bolts?",
        "answer": "Torque the terminal bolts to 60 Nm.",
        "claim": "Torque the terminal bolts to 60 Nm.",
        "cites": ["D-204#2"],
        "expected": "UNSUPPORTED",
        "note": "The cited section says 40 Nm. 60 Nm appears nowhere in the procedure. "
                "Same citation, same controls, different instruction.",
    },
    "related": {
        "question": "What torque for the terminal bolts?",
        "answer": "Torque the terminal bolts to 65 Nm.",
        "claim": "Torque the terminal bolts to 65 Nm.",
        "cites": ["D-204#4"],
        "expected": "UNSUPPORTED",
        "note": "65 Nm is a real value in the procedure - for a different component.",
    },
    "applicability": {
        "question": "Anything else after the terminal bolts?",
        "answer": "Then torque the actuator retaining bolts to 65 Nm.",
        "claim": "Torque the actuator retaining bolts to 65 Nm.",
        "cites": ["D-204#4"],
        "expected": "PARTIALLY_SUPPORTED",
        "note": "Word for word from the cited section - but D-204#3 limits it to Series B units, "
                "and nothing in the answer says so.",
    },
}


def fixture_consistency(corpus):
    """Mechanical check that the cases still say what they were built to say.

    This is NOT a judgement about support - that is the open question, and nothing here decides it. It is
    a string comparison: the normal case must quote its cited section exactly, and the cases built to
    differ from their authority must still differ. If someone edits the procedure, the exercises stop
    demonstrating anything, and the lab should say so rather than run on quietly.
    """
    problems = []
    n = CASES["normal"]
    if n["claim"] != corpus.text(n["cites"][0]):
        problems.append("the normal case no longer quotes its cited section exactly")
    for key in ("quiet", "related"):
        c = CASES[key]
        if c["claim"] == corpus.text(c["cites"][0]):
            problems.append(f"the '{key}' case now matches its cited section - it demonstrates nothing")
    return problems
