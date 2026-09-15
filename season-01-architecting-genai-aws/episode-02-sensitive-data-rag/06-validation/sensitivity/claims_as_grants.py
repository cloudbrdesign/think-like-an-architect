"""SENSITIVITY VARIANT — TEST ONLY — experiment 3 (TST-SEN-003). Never part of the normal build.

Replaces query/policy_decision.py in its own throwaway deployment. Employment status is still read from the grants
store, but domain memberships and case assignments are taken from the verified access token's `cognito:groups` claim
(`domain.<ID>` / `case.<ID>`), as if authentication claims were a current authorization source.

Expected: after a grant is revoked in the authoritative store, a still-valid token keeps retrieving the revoked domain,
so the revocation test FAILS. Authentication claims describe the identity at sign-in; they are not automatically an
authoritative source of current fine-grained authorization.
"""
import re

from core.eligibility import DENIED, UNAVAILABLE, allow, refuse
from core.reason_codes import REFUSED_AUTHORIZATION_UNAVAILABLE, REFUSED_NO_ACTIVE_EMPLOYMENT

VARIANT_MARKER = "SENSITIVITY VARIANT"
ACTIVE, INACTIVE = "ACTIVE", "INACTIVE"


def _groups(claims):
    raw = claims.get("cognito:groups")
    if isinstance(raw, list):
        return [str(g) for g in raw]
    return [g for g in re.split(r"[\s,\[\]]+", str(raw or "")) if g]


def decide(context, grants_store):
    subject = context.requester_sub
    unavailable = refuse(subject, UNAVAILABLE, REFUSED_AUTHORIZATION_UNAVAILABLE)
    try:
        current = grants_store.read_current(subject)
    except Exception:  # noqa: BLE001
        return unavailable, None
    hr = current.get("HR")
    if hr is None:
        return refuse(subject, DENIED, REFUSED_NO_ACTIVE_EMPLOYMENT), None
    employee_id, status, hr_version = hr.get("employee_id"), hr.get("employment_status"), hr.get("hr_version")
    if status != ACTIVE:
        return refuse(subject, DENIED, REFUSED_NO_ACTIVE_EMPLOYMENT, hr_version), employee_id
    grants_version = (current.get("GRANTS") or {}).get("grants_version")
    # FAULT: fine-grained entitlements come from the token, not from the authoritative store.
    groups = _groups(context.verified_claims)
    domains = [g.split(".", 1)[1] for g in groups if g.startswith("domain.")]
    cases = [g.split(".", 1)[1] for g in groups if g.startswith("case.")]
    try:
        return allow(subject, domains, cases, hr_version, grants_version), employee_id
    except ValueError:
        return unavailable, employee_id
