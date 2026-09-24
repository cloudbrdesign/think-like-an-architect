#!/usr/bin/env python3
"""Two defensible ways to decide what counts as ONE actionable claim.

Neither is a trick. An engineer could defend either in a design review. The exercise is to notice that
the serve decision is not stable across them - and that no amount of entitlement, currency, retrieval or
citation checking has anything to say about it.
"""

ANSWER = "Apply a personal lock, because the terminals remain live until the upstream breaker is opened."
CITES = ["D-204#1"]

BOUNDARIES = {
    "A · the answer is one claim": [
        {"claim": ANSWER, "carried_by_cited_section": "PARTIALLY",
         "why": "the instruction is carried; the reason given is not"},
    ],
    "B · instruction and rationale are separate claims": [
        {"claim": "Apply a personal lock.", "carried_by_cited_section": "YES",
         "why": "D-204#1 requires exactly this"},
        {"claim": "The terminals remain live until the upstream breaker is opened.",
         "carried_by_cited_section": "NO",
         "why": "the procedure never says this - it is an assertion the answer added"},
    ],
}

# A control has to act on something. This is the weakest rule anyone would defend:
# serve the answer unless a claim inside it is not carried by the authority it cites.
BLOCKING = {"NO"}


def serve(claims):
    return not any(c["carried_by_cited_section"] in BLOCKING for c in claims)
