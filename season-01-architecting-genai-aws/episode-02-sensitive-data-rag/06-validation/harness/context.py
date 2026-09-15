"""Test context: asks questions as personas through the real API and joins each response with its audit record."""
import json
import re
import time
from dataclasses import dataclass, field

from harness import canaries, client
from harness.identities import Identities
from harness.observe import Observer

CANARY = re.compile(r"CANARY-[A-Z0-9-]+")
UNIFORM = "I can't answer that from the information available to me."


@dataclass
class Observation:
    persona: str
    question: str
    status: int
    body: object
    headers: dict
    raw: str
    request_id: object
    audit: object
    token_sha256: str = ""
    extra: dict = field(default_factory=dict)

    @property
    def outcome(self):
        return (self.audit or {}).get("outcome")

    @property
    def tiers_called(self):
        return (self.audit or {}).get("tiers_called", [])

    @property
    def retrieved_keys(self):
        return sorted({f"{e['document_id']}-{e['section_id']}" for e in (self.audit or {}).get("retrieval", [])})

    @property
    def cited_keys(self):
        body = self.body if isinstance(self.body, dict) else {}
        return sorted(f"{c['document_id']}-{c['section_id']}" for c in body.get("citations", []))

    @property
    def generation_invoked(self):
        return bool(((self.audit or {}).get("generation") or {}).get("invoked"))

    @property
    def constraint_hashes(self):
        return [(c["tier"], c["sha256"]) for c in (self.audit or {}).get("constraints", [])]

    @property
    def uniform(self):
        return isinstance(self.body, dict) and self.body.get("answer") == UNIFORM and not self.body.get("citations")

    def response_canaries(self):
        return set(CANARY.findall(self.raw + json.dumps(self.headers)))

    def view(self):
        body = self.body if isinstance(self.body, dict) else {"raw": str(self.body)[:200]}
        audit = self.audit or {}
        return {"persona": self.persona, "question": self.question, "http_status": self.status,
                "request_id": self.request_id, "outcome": self.outcome,
                "failing_control": audit.get("failing_control"), "tiers_called": self.tiers_called,
                "decision": audit.get("decision") and {k: (v if k not in ("domains",) or len(v) < 50
                                                             else f"{len(v)} domains") for k, v in audit["decision"].items()},
                "constraints": audit.get("constraints"),
                "retrieved": [{k: e[k] for k in ("document_id", "section_id", "label", "scope", "record_version",
                                                 "tier", "score")} for e in audit.get("retrieval", [])],
                "verification": audit.get("verification"), "relevance": audit.get("relevance"),
                "generation_invoked": self.generation_invoked, "answer": body.get("answer"),
                "citations": body.get("citations"), "latency_ms": audit.get("latency_ms"), **self.extra}


class Context:
    def __init__(self, target, run):
        self.target, self.run = target, run
        self.ids, self.obs = Identities(target), Observer(target)
        self.personas, self.questions = canaries.personas(), canaries.questions()
        self.oracle = canaries.oracle()
        self.started_ms = int(time.time() * 1000)
        self.sent_questions, self.marks = set(), {}
        self.expiry_probe = None

    def username(self, persona):
        return self.personas[persona]["username"]

    def ineligible(self, persona):
        return set(canaries.ineligible_canaries(persona, self.oracle))

    def retrieved_canaries(self, observation):
        return {self.oracle[k]["canary"] for k in observation.retrieved_keys if k in self.oracle}

    def leaks(self, observation):
        """Ineligible canaries seen at the retrieval layer or anywhere in the response."""
        seen = self.retrieved_canaries(observation) | observation.response_canaries()
        return sorted(seen & self.ineligible(observation.persona))

    def ask(self, persona, question, token=None, extra_body=None, headers=None, query="", client_name="app"):
        text = self.questions[question]["text"] if question in self.questions else question
        self.sent_questions.add(text)
        if token is None:
            token = self.ids.token(self.username(persona), client_name)
        response = client.ask(self.target.outputs["ApiEndpoint"], token, text, extra_body, headers, query)
        audit = self.obs.audit(response.request_id) if response.request_id else None
        import hashlib
        observation = Observation(persona, question, response.status, response.body, response.headers, response.raw,
                                  response.request_id, audit, hashlib.sha256((token or "").encode()).hexdigest()[:16],
                                  {"client_retries": response.retries} if response.retries else {})
        return observation
