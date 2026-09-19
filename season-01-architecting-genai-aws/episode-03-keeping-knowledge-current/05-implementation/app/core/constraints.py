"""The mandatory eligibility constraint (CTL-011, CTL-012, CTL-013; ADR-004, D3 layer 2).

    THE CONSTRAINT, DERIVED FROM THE AUTHORITATIVE CURRENT DECISION, ENFORCES ELIGIBILITY INSIDE THE SEARCH.

Rules (SPK-E02-A):
  * Built only from a Decision. The question, document text and request fields are never inputs.
  * Positive operators only: equals, in, andAll, orAll. `notEquals` / `notIn` match chunks that LACK the attribute, so a
    negative constraint fails open (C9). validate() rejects them.
  * andAll / orAll need at least two members, so a requester with no domains gets a distinct single-condition shape.
  * Size: two limits were observed in the tested configuration — the retrieval API rejected filters above 15,360
    bytes (verification spike), and the vector store behind it rejected filters above 10,240 bytes of its own form of
    the filter (build re-measurement; about 10,265 bytes as measured here). That is MEASURED PLATFORM BEHAVIOUR, NOT AN
    ARCHITECTURAL CONSTANT. The builder refuses anything above an explicit safety budget below the lower limit, and a
    rejection by the service is a refusal too. It never truncates, never drops grants and never broadens to fit.
"""
import hashlib
import json
from dataclasses import dataclass

from core.eligibility import CONFIDENTIAL, INTERNAL, RESTRICTED
from core.reason_codes import REFUSED_CONSTRAINT_INCOMPLETE, Refusal
from core.tier_selection import RESTRICTED_TIER, SHARED

ALLOWED_OPERATORS = frozenset({"equals", "in", "andAll", "orAll"})
ALLOWED_KEYS = frozenset({"label", "scope"})
RETRIEVE_API_OBSERVED_LIMIT_BYTES = 15360          # observed: retrieval API rejection message (us-east-1)
VECTOR_STORE_OBSERVED_LIMIT_BYTES = 10240          # observed: vector-store rejection message (us-east-1, build re-measurement)
PLATFORM_OBSERVED_FILTER_LIMIT_BYTES = min(RETRIEVE_API_OBSERVED_LIMIT_BYTES, VECTOR_STORE_OBSERVED_LIMIT_BYTES)
CONSTRAINT_BUDGET_BYTES = 8192                     # explicit safety boundary: 80 % of the lower observed limit


@dataclass(frozen=True)
class TierQuery:
    tier: str
    retrieval_filter: dict
    filter_bytes: int
    filter_sha256: str


def _equals(key, value):
    return {"equals": {"key": key, "value": value}}


def _in(key, values):
    return {"in": {"key": key, "value": list(values)}}


def shared_tier_filter(decision):
    internal = _equals("label", INTERNAL)
    if not decision.domains:
        return internal                                              # orAll needs two members
    return {"orAll": [internal, {"andAll": [_equals("label", CONFIDENTIAL), _in("scope", decision.domains)]}]}


def restricted_tier_filter(decision):
    if not decision.cases:
        raise Refusal(REFUSED_CONSTRAINT_INCOMPLETE, "restricted tier without cases")   # never broaden
    return {"andAll": [_equals("label", RESTRICTED), _in("scope", decision.cases)]}


def validate(node):
    """Raise ValueError unless the filter uses only positive operators with well-formed operands."""
    if not isinstance(node, dict) or len(node) != 1:
        raise ValueError("filter node must have exactly one operator")
    operator, operand = next(iter(node.items()))
    if operator not in ALLOWED_OPERATORS:
        raise ValueError(f"operator not allowed: {operator}")
    if operator in ("andAll", "orAll"):
        if not isinstance(operand, list) or len(operand) < 2:
            raise ValueError(f"{operator} needs at least two members")
        for child in operand:
            validate(child)
        return
    if not isinstance(operand, dict) or set(operand) != {"key", "value"} or operand["key"] not in ALLOWED_KEYS:
        raise ValueError("condition must be {key, value} on label or scope")
    value = operand["value"]
    if operator == "equals" and not (isinstance(value, str) and value):
        raise ValueError("equals needs a non-empty string")
    if operator == "in" and not (isinstance(value, list) and value and all(isinstance(v, str) and v for v in value)):
        raise ValueError("in needs a non-empty list of strings")


def serialized_bytes(retrieval_filter):
    """Size as JSON with default separators — larger than the compact form, so the budget check errs on refusing."""
    return len(json.dumps(retrieval_filter, sort_keys=True).encode("utf-8"))


def sha256(retrieval_filter):
    return hashlib.sha256(json.dumps(retrieval_filter, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _tier_query(tier, retrieval_filter):
    try:
        validate(retrieval_filter)
    except ValueError as error:
        raise Refusal(REFUSED_CONSTRAINT_INCOMPLETE, str(error)) from error
    size = serialized_bytes(retrieval_filter)
    if size > CONSTRAINT_BUDGET_BYTES:
        raise Refusal(REFUSED_CONSTRAINT_INCOMPLETE, f"constraint {size} bytes exceeds budget")
    return TierQuery(tier, retrieval_filter, size, sha256(retrieval_filter))


def build_tier_queries(decision, tiers):
    """One complete constraint per selected tier, or a refusal. All or nothing: no partial set is ever returned."""
    if decision is None or not decision.allowed or not tiers:
        raise Refusal(REFUSED_CONSTRAINT_INCOMPLETE, "no allow decision")
    builders = {SHARED: shared_tier_filter, RESTRICTED_TIER: restricted_tier_filter}
    queries = []
    for tier in tiers:
        if tier not in builders:
            raise Refusal(REFUSED_CONSTRAINT_INCOMPLETE, "unknown tier")
        queries.append(_tier_query(tier, builders[tier](decision)))
    return tuple(queries)
