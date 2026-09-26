"""The authority. Everything the assistant says is judged against this, and nothing else.

A depot procedure is a set of sections. A section is IN FORCE until the records owner withdraws it.
Only this module may say whether a section is in force -- that is what "authority" means here.
"""
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Section:
    section_id: str
    text: str
    actionable: bool          # does following this change what a technician physically does?


PROCEDURE = {
    "D-204-S1": Section("D-204-S1", "Torque the terminal bolts to forty newton metres.", True),
    "D-204-S3": Section("D-204-S3", "Apply a personal lock before working on the feeder.", True),
    "D-204-S4": Section("D-204-S4", "Isolate at the upstream breaker before removing the cover.", True),
    "D-900-S1": Section("D-900-S1", "The depot's shift handover is recorded in the logbook.", False),
}


@dataclass
class RecordsSystem:
    """The authority of record. `tick` is a logical clock: no duration, no seconds, no threshold."""
    withdrawn: dict = field(default_factory=dict)   # section_id -> tick at which it was withdrawn
    tick: int = 0

    def withdraw(self, section_id, at_tick):
        if section_id not in PROCEDURE:
            raise KeyError(f"no such section: {section_id}")
        self.withdrawn[section_id] = at_tick

    def in_force(self, section_id, as_of):
        """Authoritative answer -- available ONLY when this system can be reached."""
        withdrawn_at = self.withdrawn.get(section_id)
        return withdrawn_at is None or as_of < withdrawn_at

    def snapshot(self, as_of):
        return {s: self.in_force(s, as_of) for s in PROCEDURE}
