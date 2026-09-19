"""The authoritative record's lifecycle state (CTL-030; ADR-001).

    THE RECORDS SYSTEM IS AUTHORITATIVE. THE INDEX IS DERIVED. AUTHORITY WINS ON DISAGREEMENT.

Episode 02 read three things from the classification record: label, scope and version. Incident 1 happened because that
is not the whole authoritative state. A record also carries:

    status          IN_FORCE | SUPERSEDED | WITHDRAWN | DELETED
    effective_from  when that status took effect
    superseded_by   the document that replaced it, when the status is SUPERSEDED

A document superseded by ANOTHER document keeps its own label, scope and version unchanged — which is exactly why
Episode 02's checks passed while the answer was wrong.

Nothing here reads document text. Text that claims "this supersedes MP-114" is content, never status (SEC-004).
"""
from dataclasses import dataclass
from datetime import datetime, timezone

IN_FORCE, SUPERSEDED, WITHDRAWN, DELETED = "IN_FORCE", "SUPERSEDED", "WITHDRAWN", "DELETED"
STATUSES = (IN_FORCE, SUPERSEDED, WITHDRAWN, DELETED)
SERVABLE_STATUSES = frozenset({IN_FORCE})           # everything else is never answered as current
TERMINAL_STATUSES = frozenset({DELETED})            # a deleted record is terminal for its lifetime (ADR-004)

# Problems (content-free); a record with a problem is never treated as servable.
STATUS_MISSING = "STATUS_MISSING"
STATUS_INVALID = "STATUS_INVALID"
VERSION_INVALID = "VERSION_INVALID"
EFFECTIVE_FROM_INVALID = "EFFECTIVE_FROM_INVALID"
SUPERSEDED_BY_MISSING = "SUPERSEDED_BY_MISSING"
SUPERSEDED_BY_INVALID = "SUPERSEDED_BY_INVALID"


@dataclass(frozen=True)
class RecordState:
    document_id: str
    version: int
    status: str
    effective_from: object = None        # ISO-8601 string, or None when the record does not date the change
    superseded_by: object = None
    problem: object = None

    @property
    def valid(self):
        return self.problem is None

    @property
    def servable(self):
        """Whether authority currently allows this document to be answered as current."""
        return self.valid and self.status in SERVABLE_STATUSES

    @property
    def terminal(self):
        return self.status in TERMINAL_STATUSES


def _version(value):
    return isinstance(value, int) and not isinstance(value, bool) and value >= 1


def _timestamp(value):
    if value is None:
        return True
    if not isinstance(value, str):
        return False
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
        return True
    except ValueError:
        return False


def parse(document_id, record):
    """Read the lifecycle state of one authoritative record.

    A record with no `status` is treated as IN_FORCE only if it is otherwise valid: Episode 02's records predate the
    field, and an upgrade must not silently make every old document unservable. Anything malformed is a problem, and a
    problem is never servable — unknown never means "current".
    """
    if not isinstance(record, dict):
        return RecordState(document_id, 0, WITHDRAWN, problem=STATUS_MISSING)
    version = record.get("version")
    if not _version(version):
        return RecordState(document_id, 0, WITHDRAWN, problem=VERSION_INVALID)
    status = record.get("status", IN_FORCE)
    if status is None:
        status = IN_FORCE
    if status not in STATUSES:
        return RecordState(document_id, version, WITHDRAWN, problem=STATUS_INVALID)
    effective_from = record.get("effective_from")
    if not _timestamp(effective_from):
        return RecordState(document_id, version, status, problem=EFFECTIVE_FROM_INVALID)
    superseded_by = record.get("superseded_by")
    if status == SUPERSEDED:
        if superseded_by is None:
            return RecordState(document_id, version, status, effective_from, problem=SUPERSEDED_BY_MISSING)
        if not isinstance(superseded_by, str) or not superseded_by:
            return RecordState(document_id, version, status, effective_from, problem=SUPERSEDED_BY_INVALID)
    elif superseded_by is not None and not isinstance(superseded_by, str):
        return RecordState(document_id, version, status, effective_from, problem=SUPERSEDED_BY_INVALID)
    return RecordState(document_id, version, status, effective_from, superseded_by)


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def is_effective(state, now=None):
    """True when the record's status is already in force at `now` (default: this instant).

    A change dated in the future has not happened yet; the current state still applies.
    """
    if state.effective_from is None:
        return True
    moment = datetime.fromisoformat((now or now_iso()).replace("Z", "+00:00"))
    return datetime.fromisoformat(state.effective_from.replace("Z", "+00:00")) <= moment


def states(records):
    """{document_id: record-or-None} → {document_id: RecordState}. A missing record is treated as DELETED."""
    result = {}
    for document_id, record in records.items():
        result[document_id] = (parse(document_id, record) if record is not None
                               else RecordState(document_id, 0, DELETED))
    return result
