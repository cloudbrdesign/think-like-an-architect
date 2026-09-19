"""Freshness evidence (CTL-036; ADR-007).

    PROCESSING LATENCY IS NOT PROVABLE FRESHNESS.

A fast pipeline shows how quickly the work it SAW was done. Freshness evidence answers a different set of questions:

    what authoritative state have we proven accounted for?   → the watermark per change class, and the global floor
    what is pending?                                         → the pending set
    how old is the oldest pending change?
    when was completeness last established?                  → the last completed reconciliation
    which change class is limiting the global floor?
    are we inside the approved window?
    what claim can the system make right now?

Queue depth, event age and last-successful-job time are useful OPERATIONAL metrics. They are reported separately, by
`operational()`, and never as freshness proof.
"""
from datetime import datetime, timezone

from core import convergence

# Working windows (FRS-001): engagement values for Kestrelmoor, not universal requirements.
WINDOW_SECONDS = {
    convergence.SUPERSEDE_WITHDRAW: 0,          # effective from the next request; no pending window is acceptable
    convergence.RECLASSIFY_UP: 0,
    convergence.NEW_VERSION: 4 * 3600,
    convergence.RECLASSIFY_DOWN: 24 * 3600,
    convergence.DELETION: 30 * 24 * 3600,
}
RECONCILIATION_MAX_AGE_SECONDS = 3600           # educational value; production cadence is measured, not assumed


def _moment(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00")) if isinstance(value, str) else None


def _age(value, now):
    moment = _moment(value)
    return None if moment is None else int((now - moment).total_seconds())


def claim(watermarks, pending, now=None, last_reconciliation=None):
    """The freshness statement the evidence actually supports, plus the facts behind it."""
    now = now or datetime.now(timezone.utc)
    floor = convergence.global_floor(watermarks)
    oldest = None
    for entry in pending.values():
        age = _age(entry.noticed_at, now)
        oldest = age if oldest is None else max(oldest, age)
    by_class = {}
    for change_class in convergence.CHANGE_CLASSES:
        mark = watermarks.get(change_class)
        open_items = [p for p in pending.values() if p.change_class == change_class]
        oldest_in_class = max((_age(p.noticed_at, now) or 0 for p in open_items), default=None)
        window = WINDOW_SECONDS[change_class]
        by_class[change_class] = {
            "proven_through": mark.proven_through if mark else None,
            "reconciliation_run_id": mark.reconciliation_run_id if mark else None,
            "pending": len(open_items),
            "oldest_pending_age_seconds": oldest_in_class,
            "window_seconds": window,
            "inside_window": oldest_in_class is None or oldest_in_class <= window,
        }
    reconciliation_age = _age(last_reconciliation, now)
    overdue = reconciliation_age is None or reconciliation_age > RECONCILIATION_MAX_AGE_SECONDS
    inside = all(entry["inside_window"] for entry in by_class.values())
    if floor is None or overdue:
        statement = ("NOT PROVEN — completeness has not been established for every change class; "
                     "content that cannot be confirmed current is withheld")
    elif not inside:
        statement = f"PROVEN THROUGH {floor}, but at least one change class is outside its window"
    else:
        statement = f"PROVEN THROUGH {floor}: every authoritative change effective at or before that time is applied or pending"
    return {
        "claim": statement,
        "global_floor": floor,
        "limiting_change_class": convergence.limiting_class(watermarks),
        "pending_total": len(pending),
        "oldest_pending_age_seconds": oldest,
        "last_reconciliation_completed_at": last_reconciliation,
        "reconciliation_age_seconds": reconciliation_age,
        "reconciliation_overdue": overdue,
        "inside_windows": inside,
        "by_change_class": by_class,
    }


def window_breaches(pending, now=None):
    """Which pending changes have outlived their change class's window — by class, naming the documents.

    ADR-007 §3 and OPS-001 require an alert that names THE CLASS AND THE AFFECTED IDENTIFIERS. `claim()` already
    decides the same question per class (`inside_window`) from the same WINDOW_SECONDS table; it reports ages, not
    identities, so this is a second projection of one rule rather than a second rule. The boundary matches exactly:
    `claim()` holds `age <= window` to be inside, so a breach is `age > window`.
    """
    now = _moment(now) if isinstance(now, str) else (now or datetime.now(timezone.utc))
    breached = {}
    for entry in pending.values():
        age = _age(entry.noticed_at, now)
        if age is not None and age > WINDOW_SECONDS[entry.change_class]:
            breached.setdefault(entry.change_class, []).append(entry.document_id)
    return {change_class: sorted(ids) for change_class, ids in sorted(breached.items())}


def operational(queue_depth=None, last_job_at=None, applied_last_hour=None, now=None):
    """Operational metrics. Useful, and deliberately labelled as not being freshness proof."""
    now = now or datetime.now(timezone.utc)
    return {"note": "operational metrics — they describe work observed, not work accounted for",
            "queue_depth": queue_depth, "last_successful_job_at": last_job_at,
            "last_successful_job_age_seconds": _age(last_job_at, now), "applied_last_hour": applied_last_hour}


def conservative_mode(freshness, change_class):
    """Whether this class must behave conservatively: unproven completeness, or an overdue reconciliation.

    In conservative mode safety-critical content is withheld rather than served on an unprovable claim (ADR-002).
    """
    if freshness["reconciliation_overdue"] or freshness["global_floor"] is None:
        return True
    return not freshness["by_change_class"][change_class]["inside_window"]
