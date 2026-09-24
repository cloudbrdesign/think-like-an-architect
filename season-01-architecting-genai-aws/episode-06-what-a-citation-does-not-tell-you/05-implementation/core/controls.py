#!/usr/bin/env python3
"""The controls Episodes 01-03 put in front of every answer.

Read these carefully. Each one is real, each one does its job, and NONE of them reads the answer.
"""
from . import corpus

# The rungs, kept separate on purpose. Collapsing them into one GROUNDED flag is the mistake this
# lab exists to make visible.
RUNGS = [
    ("citation_exists", "the answer cites a section identifier at all"),
    ("citation_resolves", "that identifier names a real section of the procedure"),
    ("cited_section_retrieved", "that section was actually retrieved for this request"),
    ("requester_entitled", "the requester may see it (Episode 02)"),
    ("section_in_force", "it is current, confirmed against the authority (Episode 03)"),
    ("governing_context_present", "any section that limits when it applies was also cited"),
    ("claim_supported_by_section", "the cited section actually carries the instruction given"),
]


def run(principal, cites, retrieved):
    """Every rung this system can decide mechanically. The last one is deliberately absent.

    A citation that does not resolve stops the chain: the later rungs are about a section, and there is
    no section. They report False rather than raising, so a mistyped identifier is a refusal and not a
    crash.
    """
    resolves = all(s in corpus.SECTIONS for s in cites)
    known = [s for s in cites if s in corpus.SECTIONS]
    r = {
        "citation_exists": bool(cites),
        "citation_resolves": resolves,
        "cited_section_retrieved": resolves and all(s in retrieved for s in cites),
        "requester_entitled": resolves and all(corpus.entitled(principal, s) for s in known),
        "section_in_force": resolves and all(corpus.in_force(s) for s in known),
        "governing_context_present": resolves and all(g in cites for s in known
                                                      for g in corpus.governors(s)),
        # NOT DECIDABLE HERE. Whether the cited section supports the claim is the open question of
        # Episode 06 (C-3). The lab does not compute it, and neither does any control in the system.
        "claim_supported_by_section": None,
    }
    decided = {k: v for k, v in r.items() if v is not None}
    return r, all(decided.values())


def health():
    """The operational signals an on-call engineer would look at."""
    return {"refusal_rate_within_band": True, "latency_within_budget": True,
            "error_rate_nominal": True, "retrieval_hit_rate_nominal": True}
