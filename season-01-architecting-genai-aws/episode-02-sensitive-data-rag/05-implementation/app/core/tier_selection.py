"""Tier routing and tier selection (CTL-010, CTL-012; ADR-004, D3 layer 1).

    THE TIER IS NOT THE AUTHORIZATION BOUNDARY.

Tiers reduce blast radius: RESTRICTED sections live in a separate knowledge base, bucket and index with their own
permissions, so a mistake on the shared path cannot reach them. Every tier still holds many scopes (several domains in
the shared tier, several cases in the restricted tier). Which of those a requester may see is decided by the mandatory
eligibility constraint (core/constraints.py, D3 layer 2), never by having been routed to the tier.
"""
from core.eligibility import CONFIDENTIAL, INTERNAL, RESTRICTED

SHARED, RESTRICTED_TIER = "shared", "restricted"
TIERS = (SHARED, RESTRICTED_TIER)
TIER_FOR_LABEL = {INTERNAL: SHARED, CONFIDENTIAL: SHARED, RESTRICTED: RESTRICTED_TIER}


def tier_for_label(label):
    """Ingestion routing. An unknown label has no tier (the section is never written anywhere)."""
    if label not in TIER_FOR_LABEL:
        raise ValueError("no tier for this label")
    return TIER_FOR_LABEL[label]


def select_tiers(decision):
    """Which tiers a request searches. No ALLOW decision → no tier at all (ADR-002).

    The shared tier is searched for every active requester (INTERNAL is eligible for all of them); the restricted tier
    only when the requester holds at least one case assignment. Selecting a tier grants nothing by itself.
    """
    if decision is None or not decision.allowed:
        return ()
    return (SHARED, RESTRICTED_TIER) if decision.cases else (SHARED,)
