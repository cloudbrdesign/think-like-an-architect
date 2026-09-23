#!/usr/bin/env python3
"""PUBLISHABLE CORE — the reference path: the authorised, current computation.

    current eligibility  ->  current document state  ->  retrieval  ->  generation

Every measurement in the lab is taken against THIS path. The optimisation does not get to define
its own baseline.
"""
from . import corpus

RETRIEVAL = {}


def register(question, section_ids):
    RETRIEVAL[question] = list(section_ids)


def authorised_sections(question, principal, meter):
    """Eligibility per section from CURRENT grants, then currency. Both, every time."""
    meter.add("retrieval_calls")
    ids = RETRIEVAL.get(question, [])
    meter.add("context_sections", len(ids))
    out = []
    for sid in ids:
        s = corpus.SECTIONS[sid]
        if not corpus.eligible(principal, s):
            continue
        meter.add("authority_confirmations")
        if not corpus.in_force(s):
            continue
        out.append(s)
    return out


def answer(question, principal, provider, meter):
    secs = authorised_sections(question, principal, meter)
    if not secs:
        return {"served": False, "reason": "no eligible current content", "sections": []}
    meter.add("generation_calls")
    g = provider.generate(question, secs)
    return {"served": True, "text": g["text"], "sections": [s.section_id for s in secs],
            "reason": "reference path"}
