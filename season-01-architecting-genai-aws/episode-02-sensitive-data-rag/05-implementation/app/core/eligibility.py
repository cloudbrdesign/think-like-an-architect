"""The eligibility rule and the authorization decision (CTL-001; ADR-001).

    A section is eligible for a request only if the requester is ACTIVE and
        label == INTERNAL
     or label == CONFIDENTIAL and scope ∈ the requester's domain memberships
     or label == RESTRICTED   and scope ∈ the requester's case assignments

Seniority, job title, department, the question and the document text are not inputs. A Decision is built only from
the authoritative grants store (see query/policy_decision.py); nothing a client sends can become one.
"""
import re
from dataclasses import dataclass

INTERNAL, CONFIDENTIAL, RESTRICTED = "INTERNAL", "CONFIDENTIAL", "RESTRICTED"
LABELS = (INTERNAL, CONFIDENTIAL, RESTRICTED)          # exact, case-sensitive values (SPK-E02-A C10)
RESTRICTIVENESS = {INTERNAL: 0, CONFIDENTIAL: 1, RESTRICTED: 2}
NO_SCOPE = "NONE"                                       # the scope attribute value of INTERNAL sections

ALLOW, DENIED, UNAVAILABLE = "ALLOW", "DENIED", "UNAVAILABLE"
SCOPE_ID = re.compile(r"^[A-Z0-9][A-Z0-9-]{1,62}$")


def valid_scope_id(value):
    return isinstance(value, str) and value != NO_SCOPE and bool(SCOPE_ID.match(value))


@dataclass(frozen=True)
class Decision:
    status: str
    requester: str
    domains: tuple = ()
    cases: tuple = ()
    hr_version: object = None
    grants_version: object = None
    outcome: object = None          # reason code when status is not ALLOW

    @property
    def allowed(self):
        return self.status == ALLOW


def allow(requester, domains, cases, hr_version, grants_version):
    """An ALLOW decision. Identifiers are validated, de-duplicated and sorted so equal grants give equal constraints."""
    for value in (*domains, *cases):
        if not valid_scope_id(value):
            raise ValueError("invalid domain or case identifier")
    return Decision(ALLOW, requester, tuple(sorted(set(domains))), tuple(sorted(set(cases))), hr_version,
                    grants_version)


def refuse(requester, status, outcome, hr_version=None, grants_version=None):
    if status not in (DENIED, UNAVAILABLE):
        raise ValueError("refuse() takes DENIED or UNAVAILABLE")
    return Decision(status, requester, (), (), hr_version, grants_version, outcome)


def is_eligible(decision, label, scope):
    """The rule itself. Anything that is not an exact, recognised combination is not eligible."""
    if not isinstance(decision, Decision) or not decision.allowed:
        return False
    if label == INTERNAL:
        return scope == NO_SCOPE
    if label == CONFIDENTIAL:
        return scope in decision.domains
    if label == RESTRICTED:
        return scope in decision.cases
    return False
