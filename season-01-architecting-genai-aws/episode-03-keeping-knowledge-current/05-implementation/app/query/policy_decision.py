"""Policy decision point: the per-request authorization decision (CTL-001, CTL-003, CTL-004; ADR-002).

    AUTHENTICATED IS NOT AUTHORISED.
    NO AUTHORITATIVE CURRENT GRANTS = NO RETRIEVAL.

For every request the grants store is read again, with consistent reads: employment status and version (HR record),
domain memberships, case assignments and version (GRANTS record). Nothing is cached in a warm function, so a revocation
or a departure applies to the very next request.

Fail closed:
  * store error, timeout or incomplete read  → UNAVAILABLE  (REFUSED_AUTHORIZATION_UNAVAILABLE)
  * malformed authorization data             → UNAVAILABLE  (REFUSED_AUTHORIZATION_UNAVAILABLE)
  * no employment record, or not ACTIVE      → DENIED       (REFUSED_NO_ACTIVE_EMPLOYMENT)
There is no degraded mode: an UNAVAILABLE decision never falls back to INTERNAL-only retrieval (ADR-002).

Token claims (`cognito:groups` and the rest) describe the identity at sign-in; they are ignored here.
"""
from core.eligibility import DENIED, UNAVAILABLE, allow, refuse, valid_scope_id
from core.reason_codes import REFUSED_AUTHORIZATION_UNAVAILABLE, REFUSED_NO_ACTIVE_EMPLOYMENT

ACTIVE, INACTIVE = "ACTIVE", "INACTIVE"


def _version(value):
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 1 else None


def decide(context, grants_store):
    """Return (Decision, employee_id or None)."""
    subject = context.requester_sub
    unavailable = refuse(subject, UNAVAILABLE, REFUSED_AUTHORIZATION_UNAVAILABLE)
    try:
        current = grants_store.read_current(subject)
    except Exception:  # noqa: BLE001 — any failure to read means authorization cannot be established
        return unavailable, None
    hr = current.get("HR")
    if hr is None:
        return refuse(subject, DENIED, REFUSED_NO_ACTIVE_EMPLOYMENT), None
    employee_id, status, hr_version = hr.get("employee_id"), hr.get("employment_status"), _version(hr.get("hr_version"))
    if not isinstance(employee_id, str) or status not in (ACTIVE, INACTIVE) or hr_version is None:
        return unavailable, None
    if status != ACTIVE:
        return refuse(subject, DENIED, REFUSED_NO_ACTIVE_EMPLOYMENT, hr_version), employee_id
    grants = current.get("GRANTS")
    if grants is None:
        return unavailable, employee_id
    domains, cases, grants_version = grants.get("domains"), grants.get("cases"), _version(grants.get("grants_version"))
    if (grants_version is None or not isinstance(domains, list) or not isinstance(cases, list)
            or not all(valid_scope_id(v) for v in domains + cases)):
        return unavailable, employee_id
    return allow(subject, domains, cases, hr_version, grants_version), employee_id
