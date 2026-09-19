"""Per-document generations and the switch (CTL-033; ADR-005).

    NO ANSWER MIXES TWO VERSIONS OF A DOCUMENT.

A document's derived content is written as a COMPLETE generation, identified by the authoritative version it was built
from. Nothing in a generation is retrievable until the whole generation is complete; the serving reference is then
switched in one step, and the previous generation is retired afterwards.

    BUILD  →  VERIFY  →  SWITCH  →  RETIRE

A failed build leaves the previous generation serving and the document pending (ADR-002) — never a half-written mixture.
Section identifiers carry the generation, so two versions of a document can coexist in the store without ever being
candidates at the same time: only the switched-to generation is attached to the serving reference.
"""
from dataclasses import dataclass

from core import change_apply

BUILDING, VERIFIED, SERVING, RETIRED = "BUILDING", "VERIFIED", "SERVING", "RETIRED"
STATES = (BUILDING, VERIFIED, SERVING, RETIRED)

# Problems that stop a switch (content-free).
INCOMPLETE = "INCOMPLETE"
ATTRIBUTE_MISMATCH = "ATTRIBUTE_MISMATCH"
EMPTY = "EMPTY"


def generation_id(document_id, version):
    return f"{document_id}#g{int(version)}"


def custom_document_id(document_id, section_id, version):
    """The knowledge-base document identifier. It carries the generation, so retiring one cannot delete the other."""
    return f"{document_id}-{section_id}-g{int(version)}"


def parse_custom_document_id(identifier):
    """('D-03', 'S4', 7) from 'D-03-S4-g7'; ValueError if it is not one of ours."""
    try:
        head, generation = identifier.rsplit("-g", 1)
        document_id, section_id = head.rsplit("-", 1)
        return document_id, section_id, int(generation)
    except (ValueError, AttributeError) as error:
        raise ValueError(f"not a generation document identifier: {identifier!r}") from error


def object_key(document_id, section_id, version):
    return f"sections/{document_id}/g{int(version)}/{section_id}.txt"


@dataclass(frozen=True)
class Generation:
    document_id: str
    version: int
    state: str
    section_ids: tuple = ()
    problem: object = None

    @property
    def id(self):
        return generation_id(self.document_id, self.version)

    @property
    def complete(self):
        return self.problem is None and bool(self.section_ids)

    def item(self):
        return {"generation_id": self.id, "document_id": self.document_id, "version": self.version,
                "state": self.state, "section_ids": list(self.section_ids), "problem": self.problem}


def verify(document_id, version, expected_section_ids, written):
    """Check a built generation before it may serve.

    `written` is {section_id: attributes-as-indexed}. Every expected section must be present, and every section's
    attributes must carry this document, this section and this authoritative version — so a generation can never serve
    content labelled for another version.
    """
    expected = tuple(sorted(expected_section_ids))
    if not expected:
        return Generation(document_id, version, BUILDING, (), EMPTY)
    missing = [s for s in expected if s not in written]
    if missing:
        return Generation(document_id, version, BUILDING, tuple(sorted(written)), INCOMPLETE)
    for section_id, attributes in sorted(written.items()):
        if (attributes.get("document_id") != document_id or attributes.get("section_id") != section_id
                or str(attributes.get("record_version")) != str(version)):
            return Generation(document_id, version, BUILDING, expected, ATTRIBUTE_MISMATCH)
    return Generation(document_id, version, VERIFIED, expected)


class Regression(ValueError):
    """A promotion refused because it would move derived state backwards (AB-14)."""


def switch(generation, reflected, status=None):
    """Promote a verified generation to serving. A generation that is not verified never serves.

    `reflected` is what derived state serves for this document RIGHT NOW, and it is REQUIRED — not optional and not
    defaulted. This is the one place a generation becomes the serving one, so it is the one place the monotonic
    invariant can be enforced for every path at once: incremental apply, reconciliation repair, operator repair and
    rebuild all arrive here. Rebuild reached this line without ever passing the applier's ordering decision and moved
    a document backwards (AB-14); requiring the current state as an argument is what makes that hard to repeat, since
    a caller cannot promote without first saying what it is replacing.

    Pass a state read at SWITCH time. A build takes seconds to minutes and another path may have promoted a newer
    generation meanwhile — the ADR-005 / AB-11 lesson, applied to promotion rather than to retirement.
    """
    if generation.state != VERIFIED or not generation.complete:
        raise ValueError(f"generation {generation.id} is {generation.state}, not verified")
    if not change_apply.may_promote(reflected, generation.version, status):
        raise Regression(f"generation {generation.id} would replace serving version "
                         f"{getattr(reflected, 'version', None)} with {generation.version}")
    return Generation(generation.document_id, generation.version, SERVING, generation.section_ids)


def may_retire(candidate_version, promoted_version):
    """Whether the operation that just promoted `promoted_version` may retire `candidate_version` (AB-16).

    Only a STRICTLY OLDER generation may be retired. A build writes its generation and its derived copies before it
    switches, so a concurrent operation can see a newer generation that is VERIFIED and not yet promoted — or one
    that has already promoted while this slower operation was still working. Retiring either destroys artefacts
    belonging to a promotion that has advanced beyond this one: observed on the deployment as
    `applied D-06 v12, retired ["D-06#g11", "D-06#g13"]`, which left D-06 serving a generation whose section object
    had been deleted. Reconciliation compares versions, so it cannot see a missing object.

    This is the converse of the two protections already in place, and neither covers it: AB-11 stops a leaked OLDER
    generation staying retrievable (still true — an older generation is retired here), and AB-14 governs which
    generation may BECOME serving, not which artefacts a completing operation may DESTROY.
    """
    return int(candidate_version) < int(promoted_version)


def retire(generation):
    return Generation(generation.document_id, generation.version, RETIRED, generation.section_ids)
