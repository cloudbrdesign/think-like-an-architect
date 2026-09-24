#!/usr/bin/env python3
"""The procedure Kestrelmoor's assistant answers from.

SYNTHETIC. Authored for this lab so that, for every case you run, what the procedure does and does not
say is fixed and inspectable. That is the only reason this lab can talk about support at all.
"""

DOC, TITLE = "D-204", "Feeder pillar maintenance — Series A and Series B"

SECTIONS = {
    "D-204#1": {"heading": "Isolation", "in_force": True,
                "text": "Isolate the feeder at the local disconnect and apply a personal lock "
                        "before any work begins."},
    "D-204#2": {"heading": "Terminal bolts", "in_force": True,
                "text": "Torque the terminal bolts to 40 Nm."},
    "D-204#3": {"heading": "Applicability", "in_force": True,
                "text": "Sections 4 and 5 apply only to units fitted with the Series B actuator."},
    "D-204#4": {"heading": "Actuator retaining bolts", "in_force": True,
                "text": "Then torque the actuator retaining bolts to 65 Nm."},
    "D-204#5": {"heading": "Function check", "in_force": True,
                "text": "Complete a function check and record the result in the maintenance log."},
}

# Which sections govern the reading of which others. D-204#3 limits when #4 and #5 apply at all.
GOVERNED_BY = {"D-204#4": ["D-204#3"], "D-204#5": ["D-204#3"]}

ENTITLEMENTS = {"tech-4417": {"D-204"}}


def entitled(principal, sid):
    return sid.split("#")[0] in ENTITLEMENTS.get(principal, set())


def in_force(sid):
    return SECTIONS[sid]["in_force"]


def text(sid):
    return SECTIONS[sid]["text"]


def governors(sid):
    return GOVERNED_BY.get(sid, [])
