"""Security-sensitive parser: verified group claim → EXACTLY ONE TENANT, or DENY.

Why this module exists (platform finding CH-12):
    Cognito puts group membership in the access token as a JSON array. But when the API Gateway HTTP API JWT
    authorizer passes verified claims to the function, EVERY claim arrives as a string. Groups arrive as
        "[tenant-a]"            one group
        "[tenant-a tenant-b]"   two groups (space separated)
    and a user with no groups has no claim at all.

The rule is deliberately strict. Loose parsing — splitting on commas, trimming brackets, taking the first group —
could turn an ambiguous or malformed claim into a tenant. Anything that is not exactly one well-formed tenant group
fails closed.
"""
import re

from shared.reason_codes import TENANT_CLAIM_AMBIGUOUS, TENANT_CLAIM_MISSING, Denied

TENANT_ID_PATTERN = re.compile(r"tenant-[a-z0-9-]{1,40}")
_EXACTLY_ONE_GROUP = re.compile(r"\[(tenant-[a-z0-9-]{1,40})\]")
_SPACE_SEPARATED_GROUPS = re.compile(r"\[[^\[\]\s]+(?: [^\[\]\s]+)+\]")


def is_tenant_id(value):
    return isinstance(value, str) and TENANT_ID_PATTERN.fullmatch(value) is not None


def parse_tenant_group_claim(raw):
    """Return the single tenant ID carried by the verified `cognito:groups` claim, or raise Denied."""
    if raw is None:
        raise Denied(TENANT_CLAIM_MISSING, "no group claim: the user belongs to no group")
    if not isinstance(raw, str):
        raise Denied(TENANT_CLAIM_AMBIGUOUS, f"group claim has unexpected type {type(raw).__name__}")
    if raw in ("", "[]"):
        raise Denied(TENANT_CLAIM_MISSING, "empty group claim")
    match = _EXACTLY_ONE_GROUP.fullmatch(raw)
    if match:
        return match.group(1)
    if _SPACE_SEPARATED_GROUPS.fullmatch(raw):
        raise Denied(TENANT_CLAIM_AMBIGUOUS, "more than one group: exactly one tenant membership is required")
    raise Denied(TENANT_CLAIM_AMBIGUOUS, "group claim does not have the expected syntax")
