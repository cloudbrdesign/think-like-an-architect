"""TEST-ONLY SENSITIVITY VARIANT — DELIBERATELY BROKEN. NEVER PART OF A NORMAL BUILD. (TST-SEN-011)

This file replaces app/shared/retrieval_scope.py ONLY in `scripts/build.sh sensitivity`, which deploys a separately
named, separately tagged stack that `scripts/sensitivity-run.sh` destroys in the same run.

Exactly one thing is different: build_tenant_filter() returns a predicate that constrains nothing
    {"notEquals": {"key": "owning_tenant", "value": "__sensitivity-variant-no-such-tenant__"}}
so every attributed chunk of every tenant becomes a retrieval candidate. The API, the retrieval client, ownership
verification (CTL-017), citations and audit are unchanged — ownership verification stays ON on purpose.

Expected result: the cross-tenant isolation tests FAIL, because other tenants' documents appear in the audit record's
`retrieved` list, and ownership verification withholds the response (OWNERSHIP_MISMATCH). That proves the tests observe
the retrieval layer and can detect the primary control disappearing.
"""
import hashlib
import json
from dataclasses import dataclass, field

from shared.reason_codes import RETRIEVAL_SCOPE_INVALID, Denied
from shared.tenant_claims import is_tenant_id

OWNER_ATTRIBUTE = "owning_tenant"
NUMBER_OF_RESULTS = 5
SENSITIVITY_SENTINEL = "__sensitivity-variant-no-such-tenant__"
_ISSUED_HERE = object()


@dataclass(frozen=True)
class TenantScopedQuery:
    tenant_id: str
    question: str
    filter_json: str
    number_of_results: int
    issued_by: object = field(repr=False, compare=False, default=None)

    def __post_init__(self):
        if self.issued_by is not _ISSUED_HERE:
            raise Denied(RETRIEVAL_SCOPE_INVALID, "scoped query not issued by authorize_and_scope")

    @property
    def retrieval_filter(self):
        return json.loads(self.filter_json)


def build_tenant_filter(ctx):
    """SENSITIVITY VARIANT: the primary control is removed. This predicate matches every tenant's chunks."""
    tenant_id = getattr(ctx, "tenant_id", None)
    if not is_tenant_id(tenant_id):
        raise Denied(RETRIEVAL_SCOPE_INVALID, "no valid tenant in context")
    return {"notEquals": {"key": OWNER_ATTRIBUTE, "value": SENSITIVITY_SENTINEL}}


def authorize_and_scope(ctx, action, question):
    if action != "ask":
        raise Denied(RETRIEVAL_SCOPE_INVALID, f"action '{action}' is not a retrieval action")
    tenant_filter = build_tenant_filter(ctx)
    return TenantScopedQuery(
        tenant_id=ctx.tenant_id,
        question=question,
        filter_json=json.dumps(tenant_filter, sort_keys=True, separators=(",", ":")),
        number_of_results=NUMBER_OF_RESULTS,
        issued_by=_ISSUED_HERE,
    )


def constraint_record(scoped):
    (operator, body), = scoped.retrieval_filter.items()
    return {"attribute": body["key"], "operator": operator, "value": body["value"]}


def constraint_sha256(scoped):
    return hashlib.sha256(scoped.filter_json.encode("utf-8")).hexdigest()
