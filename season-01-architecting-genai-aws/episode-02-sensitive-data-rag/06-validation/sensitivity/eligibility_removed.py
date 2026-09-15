"""SENSITIVITY VARIANT — TEST ONLY — experiment 1 (TST-SEN-001). Never part of the normal build.

Replaces core/constraints.py in its own throwaway deployment. The eligibility clauses are REMOVED: both tiers are
searched for every requester, constrained by label only — no domain or case scope. The decision is still computed,
and before-generation verification is unchanged.

Expected: the negative eligibility tests FAIL at the retrieval layer (ineligible chunks appear in the audit record's
retrieval list), and verification withholds the answers. That is detection and containment AFTER the security boundary
failed — not the architecture remaining safe.
"""
import hashlib
import json
from dataclasses import dataclass

from core.reason_codes import REFUSED_CONSTRAINT_INCOMPLETE, Refusal
from core.tier_selection import RESTRICTED_TIER, SHARED

VARIANT_MARKER = "SENSITIVITY VARIANT"
CONSTRAINT_BUDGET_BYTES = 8192


@dataclass(frozen=True)
class TierQuery:
    tier: str
    retrieval_filter: dict
    filter_bytes: int
    filter_sha256: str


def _query(tier, retrieval_filter):
    text = json.dumps(retrieval_filter, sort_keys=True)
    digest = hashlib.sha256(json.dumps(retrieval_filter, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return TierQuery(tier, retrieval_filter, len(text.encode()), digest)


def build_tier_queries(decision, tiers):
    if decision is None or not decision.allowed:
        raise Refusal(REFUSED_CONSTRAINT_INCOMPLETE, "no allow decision")
    # FAULT: `tiers` and the decision's domains and cases are ignored.
    shared = {"orAll": [{"equals": {"key": "label", "value": "INTERNAL"}},
                        {"equals": {"key": "label", "value": "CONFIDENTIAL"}}]}
    restricted = {"equals": {"key": "label", "value": "RESTRICTED"}}
    return (_query(SHARED, shared), _query(RESTRICTED_TIER, restricted))
