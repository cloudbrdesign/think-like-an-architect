"""The obligation-to-class mapping -- GOVERNED STATE, not a configuration file.

It answers one question: does an answer of this class require the CURRENT confirmation of authority?

Two responsibilities, and they are separate:
  * the records / document owner owns the mapping's CONTENT and its lifecycle, with the corpus;
  * Safety & Compliance owns the AUTHORITY to declare that a class may be served without current
    confirmation of a safety obligation.

So an entry is only usable when it carries BOTH: content attributable to the records owner, and an
exemption declaration attributable to Safety & Compliance. A records owner who edits content cannot
thereby create an exemption. An entry missing either is not an entry.
"""
from dataclasses import dataclass

RECORDS_OWNER = "records-and-documents-owner"
SAFETY = "safety-and-compliance"


@dataclass(frozen=True)
class Entry:
    section_id: str
    requires_current_confirmation: bool
    basis: str
    content_owner: str
    exemption_declared_by: str | None     # required ONLY when an obligation is being waived
    version: str

    def is_authoritative(self):
        if self.content_owner != RECORDS_OWNER:
            return False, "content not attributable to the records / document owner"
        if not self.requires_current_confirmation and self.exemption_declared_by != SAFETY:
            return False, "exemption not declared by Safety & Compliance"
        return True, "attributable"


VERSION = "mapping-2026-09-26.1"

AUTHORED = {
    "D-204-S1": Entry("D-204-S1", True, "actionable instruction; a withdrawal changes what must be done",
                      RECORDS_OWNER, None, VERSION),
    "D-204-S3": Entry("D-204-S3", True, "actionable instruction", RECORDS_OWNER, None, VERSION),
    "D-204-S4": Entry("D-204-S4", True, "actionable instruction", RECORDS_OWNER, None, VERSION),
    "D-900-S1": Entry("D-900-S1", False, "descriptive convention; no instruction is carried",
                      RECORDS_OWNER, SAFETY, VERSION),
}


class Mapping:
    """Fail-closed by construction. There is no code path on which a missing entry means 'serve'."""

    def __init__(self, entries=None, reachable=True, fetch_route=None):
        self.entries = dict(AUTHORED if entries is None else entries)
        self.reachable = reachable
        self.fetch_route = fetch_route

    def lookup(self, section_id, broken_route=None):
        """Returns (requires_current_confirmation | None, reason). None means NOT DETERMINABLE."""
        if not self.reachable or (self.fetch_route and self.fetch_route == broken_route):
            return None, "mapping unreachable on this path"
        entry = self.entries.get(section_id)
        if entry is None:
            return None, "class unmapped"
        ok, why = entry.is_authoritative()
        if not ok:
            return None, why
        return entry.requires_current_confirmation, f"{entry.basis} [{entry.version}]"

    def describe(self):
        return {"version": VERSION, "entries": len(self.entries), "reachable": self.reachable,
                "fetch_route": self.fetch_route}
