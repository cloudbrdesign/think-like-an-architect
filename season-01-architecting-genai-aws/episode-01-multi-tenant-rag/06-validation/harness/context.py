"""Shared state for one harness run, and the helpers every suite uses."""
import subprocess
import sys
import time

from harness import canary, fixtures
from harness.client import Api
from harness.common import TESTS, load_fixtures
from harness.identities import Identities
from harness.observe import Observer


class Context:
    def __init__(self, target, run):
        self.target, self.run = target, run
        self.ids = Identities(target)
        self.api = Api(target.outputs["ApiEndpoint"])
        self.obs = Observer(target)
        self.data = load_fixtures()
        self.q = self.data["questions"]
        self.state = fixtures.load_state(target)
        self.start_ms = int(time.time() * 1000) - 60_000
        self.event_ids = []
        self.responses = {}
        self.expiry_probe = None

    # ── ownership map (independent of the index's own attributes) ──
    def own(self, tenant_id):
        return fixtures.tenant_documents(self.state, tenant_id)

    def doc(self, key):
        return fixtures.document_id(self.state, key)

    def tenant_user(self, tenant_id):
        return next(t["user"] for t in self.data["tenants"] if t["tenant_id"] == tenant_id)

    # ── actions ──
    def ask(self, user, question, **kwargs):
        token = kwargs.pop("token", None) or self.ids.access(user)
        response = self.api.call("POST", "/ask", token=token, body=kwargs.pop("body", {"question": question}), **kwargs)
        record = self.obs.audit(response.event_id) if response.event_id else None
        if response.event_id:
            self.event_ids.append(response.event_id)
        return response, record

    def leak_findings(self, own_tenant, response, record):
        """Everything that crossed a boundary it should not have: the retrieval layer first, then every channel."""
        retrieved = (record or {}).get("retrieved") or []
        own_ids = self.own(own_tenant)
        foreign_retrieved = [r for r in retrieved if r.get("owner_attribute") != own_tenant or r.get("document_id") not in own_ids]
        citations = (response.body or {}).get("citations", []) if isinstance(response.body, dict) else []
        foreign_citations = [c for c in citations if c.get("document_id") not in own_ids]
        return {"foreign_retrieved": foreign_retrieved, "foreign_citations": foreign_citations,
                "foreign_canaries": canary.foreign_hits(own_tenant, response.body, response.headers, record),
                "verification_outcome": (record or {}).get("verification_outcome")}

    @staticmethod
    def is_leak(findings):
        return bool(findings["foreign_retrieved"] or findings["foreign_citations"] or findings["foreign_canaries"]
                    or findings["verification_outcome"] == "OWNERSHIP_MISMATCH")

    def component_tests(self, names):
        """Run named component tests (06-validation/tests) in a separate interpreter; return (passed, output tail)."""
        result = subprocess.run([sys.executable, "-B", "-m", "unittest", *names], cwd=TESTS, capture_output=True, text=True)
        tail = (result.stderr or result.stdout).strip().splitlines()[-3:]
        return result.returncode == 0, tail


def audit_view(record):
    """The investigation-relevant part of an audit record (it never contains content)."""
    if not record:
        return None
    keys = ("event_id", "tenant_context", "decision", "reason_code", "failed_control", "constraint", "retrieved",
            "verification_outcome", "discarded_count", "cited_document_ids", "outcome", "status_code", "variant",
            "latency_ms")  # latency_ms: server-side, measured by the function (NFR-001 evidence)
    return {k: record.get(k) for k in keys}
