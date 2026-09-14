"""THE PRIMARY PREVENTIVE ISOLATION CONTROL (CTL-015), with the authorisation decision (CTL-007). ADR-003, ADR-005.

This is the only place in the application where the tenant constraint is built.

    authorize_and_scope(ctx, action, question) → TenantScopedQuery

The constraint is
    {"equals": {"key": "owning_tenant", "value": <ctx.tenant_id>}}
and it is evaluated by the retrieval index DURING the search, so another tenant's chunks are never candidates.

What cannot influence it — by construction, not by instruction:
  - question text, prompt instructions and model output: the question is carried as data and never parsed here;
  - caller-supplied tenant values: the only input is the TenantContext resolved from verified claims + registry;
  - the retrieval client: it can only send a TenantScopedQuery issued by this module (see retrieval_client.py).

There is no flag, parameter or environment variable that weakens this constraint. The sensitivity test (TST-SEN-011)
replaces this whole file in a separate, test-only build and deployment; see 06-validation/sensitivity/.
"""
import hashlib
import json
from dataclasses import dataclass, field

from shared.reason_codes import RETRIEVAL_SCOPE_INVALID, Denied
from shared.tenant_claims import is_tenant_id

OWNER_ATTRIBUTE = "owning_tenant"
NUMBER_OF_RESULTS = 5
_ISSUED_HERE = object()  # only this module can issue a TenantScopedQuery


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
    """The mandatory single-tenant constraint. It takes the trusted context and nothing else."""
    tenant_id = getattr(ctx, "tenant_id", None)
    if not is_tenant_id(tenant_id):
        raise Denied(RETRIEVAL_SCOPE_INVALID, "no valid tenant in context")
    return {"equals": {"key": OWNER_ATTRIBUTE, "value": tenant_id}}


def authorize_and_scope(ctx, action, question):
    """Authorisation decision and retrieval constraint in one code path. Returns a scoped query only on ALLOW."""
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
    """The applied constraint as recorded in the audit record, derived from the filter actually sent."""
    (operator, body), = scoped.retrieval_filter.items()
    return {"attribute": body["key"], "operator": operator, "value": body["value"]}


def constraint_sha256(scoped):
    return hashlib.sha256(scoped.filter_json.encode("utf-8")).hexdigest()
