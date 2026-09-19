"""The currency core: authoritative lifecycle state, convergence, freshness evidence, generations, deletion, ordering.

These tests are the written form of the four invariants. They need no AWS account: every rule that decides whether a
document may be answered as current is a pure function of the authoritative record and the derived state.
"""
import unittest

import support  # noqa: F401 — puts app/ on the import path
from core import change_apply as ca, convergence as cv, deletion as dl, freshness as fr, generations as gn
from core import record_state as rs


def view(pending=(), watermarks=(), available=True):
    return cv.ConvergenceView({p.document_id: p for p in pending},
                              {w.change_class: w for w in watermarks}, available=available)


def watermark(change_class, proven_through="2026-09-16T10:00:00+00:00"):
    return cv.Watermark(change_class, proven_through, "rec-1", proven_through, 15)


def all_proven(proven_through="2026-09-16T10:00:00+00:00"):
    return [watermark(c, proven_through) for c in cv.CHANGE_CLASSES]


class AuthoritativeLifecycle(unittest.TestCase):
    """ADR-001: status, effective_from and supersession are authoritative — and never read from document text."""

    def test_record_without_a_status_field_stays_servable(self):
        """Episode 02's records predate the field; an upgrade must not make every existing document unservable."""
        state = rs.parse("D-01", support.lifecycle(version=2))
        self.assertEqual((state.status, state.servable, state.valid), (rs.IN_FORCE, True, True))

    def test_superseded_document_is_not_servable_although_its_label_and_version_are_unchanged(self):
        """Incident 1 in one assertion: label, scope and version all still check out, and the answer is still wrong."""
        record = support.lifecycle(version=1, status=rs.SUPERSEDED, superseded_by="D-06")
        state = rs.parse("D-01", record)
        self.assertEqual((state.status, state.version), (rs.SUPERSEDED, 1))
        self.assertFalse(state.servable)

    def test_withdrawn_and_deleted_are_not_servable(self):
        for status in (rs.WITHDRAWN, rs.DELETED):
            self.assertFalse(rs.parse("D-01", support.lifecycle(status=status)).servable)

    def test_supersession_without_a_successor_is_a_problem_not_a_current_document(self):
        state = rs.parse("D-01", support.lifecycle(status=rs.SUPERSEDED))
        self.assertEqual(state.problem, rs.SUPERSEDED_BY_MISSING)
        self.assertFalse(state.servable)

    def test_malformed_records_are_never_servable(self):
        cases = {rs.STATUS_INVALID: support.lifecycle(status="RETIRED"),
                 rs.VERSION_INVALID: support.lifecycle(version=0),
                 rs.EFFECTIVE_FROM_INVALID: support.lifecycle(status=rs.WITHDRAWN, effective_from="soon"),
                 rs.SUPERSEDED_BY_INVALID: support.lifecycle(status=rs.SUPERSEDED, superseded_by=["D-06"])}
        for problem, record in cases.items():
            state = rs.parse("D-01", record)
            self.assertEqual(state.problem, problem)
            self.assertFalse(state.servable, problem)

    def test_a_missing_record_is_treated_as_deleted(self):
        self.assertEqual(rs.states({"D-99": None})["D-99"].status, rs.DELETED)

    def test_a_future_dated_status_change_has_not_happened_yet(self):
        state = rs.parse("D-01", support.lifecycle(status=rs.WITHDRAWN, effective_from="2026-09-16T12:00:00+00:00"))
        self.assertFalse(rs.is_effective(state, now="2026-09-16T11:59:59+00:00"))
        self.assertTrue(rs.is_effective(state, now="2026-09-16T12:00:00+00:00"))


class ConvergenceState(unittest.TestCase):
    """ADR-002: four states, and only one of them may be served."""

    def state(self, record, pending=(), watermarks=(), available=True, now=None):
        return cv.classify("D-01", rs.parse("D-01", record), view(pending, watermarks, available), now)

    def test_in_force_and_nothing_pending_is_current(self):
        self.assertEqual(self.state(support.lifecycle()), cv.KNOWN_CURRENT)

    def test_a_known_change_makes_it_pending_before_any_content_work_happens(self):
        pending = cv.Pending("D-01", cv.SUPERSEDE_WITHDRAW, 2, "2026-09-16T10:00:00+00:00")
        self.assertEqual(self.state(support.lifecycle(), [pending]), cv.KNOWN_PENDING)

    def test_superseded_is_gone(self):
        record = support.lifecycle(status=rs.SUPERSEDED, superseded_by="D-06")
        self.assertEqual(self.state(record), cv.KNOWN_GONE)

    def test_a_future_dated_supersession_is_still_current(self):
        record = support.lifecycle(status=rs.SUPERSEDED, superseded_by="D-06",
                                   effective_from="2026-09-16T12:00:00+00:00")
        self.assertEqual(self.state(record, now="2026-09-16T11:00:00+00:00"), cv.KNOWN_CURRENT)

    def test_an_unreadable_convergence_store_is_unknown_never_empty(self):
        self.assertEqual(self.state(support.lifecycle(), available=False), cv.UNKNOWN)

    def test_an_invalid_record_is_unknown_not_current(self):
        self.assertEqual(self.state(support.lifecycle(status="RETIRED")), cv.UNKNOWN)

    def test_only_known_current_is_servable(self):
        self.assertEqual([s for s in cv.STATES if cv.servable(s)], [cv.KNOWN_CURRENT])


class Watermarks(unittest.TestCase):
    """ADR-007: the floor is conservative, and one unproven class is enough to make the whole claim unproven."""

    def test_the_floor_is_the_oldest_proven_moment(self):
        marks = {w.change_class: w for w in all_proven()}
        marks[cv.NEW_VERSION] = watermark(cv.NEW_VERSION, "2026-09-16T08:00:00+00:00")
        self.assertEqual(cv.global_floor(marks), "2026-09-16T08:00:00+00:00")
        self.assertEqual(cv.limiting_class(marks), cv.NEW_VERSION)

    def test_one_unproven_class_makes_the_floor_unproven(self):
        marks = {w.change_class: w for w in all_proven()}
        marks[cv.DELETION] = cv.Watermark(cv.DELETION)
        self.assertIsNone(cv.global_floor(marks))
        self.assertEqual(cv.limiting_class(marks), cv.DELETION)


class ChangeClassification(unittest.TestCase):
    """A change that is several things at once is reported as the most consequential one."""

    def state(self, status=None, superseded_by=None):
        return rs.parse("D-01", support.lifecycle(status=status, superseded_by=superseded_by))

    def test_removal_is_a_deletion(self):
        self.assertEqual(cv.change_class_for(self.state(), None), cv.DELETION)
        self.assertEqual(cv.change_class_for(self.state(), self.state(rs.DELETED)), cv.DELETION)

    def test_supersession_outranks_reclassification(self):
        after = self.state(rs.SUPERSEDED, "D-06")
        self.assertEqual(cv.change_class_for(self.state(), after, "INTERNAL", "RESTRICTED"), cv.SUPERSEDE_WITHDRAW)

    def test_reclassification_outranks_a_new_version(self):
        self.assertEqual(cv.change_class_for(self.state(), self.state(), "INTERNAL", "CONFIDENTIAL"), cv.RECLASSIFY_UP)
        self.assertEqual(cv.change_class_for(self.state(), self.state(), "CONFIDENTIAL", "INTERNAL"),
                         cv.RECLASSIFY_DOWN)

    def test_otherwise_it_is_a_new_version(self):
        self.assertEqual(cv.change_class_for(self.state(), self.state(), "INTERNAL", "INTERNAL"), cv.NEW_VERSION)

    def test_the_safety_critical_classes_are_the_ones_with_no_tolerated_window(self):
        self.assertEqual(sorted(cv.SAFETY_CRITICAL_CLASSES),
                         sorted(c for c in cv.CHANGE_CLASSES if fr.WINDOW_SECONDS[c] == 0 or c == cv.DELETION))


class FreshnessEvidence(unittest.TestCase):
    """CTL-036: what the system may claim, as opposed to how fast it processed what it happened to see."""

    def claim(self, watermarks=None, pending=(), reconciled="2026-09-16T09:55:00+00:00",
              now="2026-09-16T10:00:00+00:00"):
        from datetime import datetime
        marks = {w.change_class: w for w in (watermarks if watermarks is not None else all_proven())}
        return fr.claim(marks, {p.document_id: p for p in pending},
                        now=datetime.fromisoformat(now), last_reconciliation=reconciled)

    def test_a_proven_floor_and_a_recent_pass_support_a_claim(self):
        result = self.claim()
        self.assertTrue(result["claim"].startswith("PROVEN THROUGH"))
        self.assertFalse(fr.conservative_mode(result, cv.SUPERSEDE_WITHDRAW))

    def test_an_overdue_reconciliation_cannot_be_rescued_by_an_old_watermark(self):
        result = self.claim(reconciled="2026-09-16T08:00:00+00:00")
        self.assertTrue(result["reconciliation_overdue"])
        self.assertTrue(result["claim"].startswith("NOT PROVEN"))
        self.assertTrue(fr.conservative_mode(result, cv.NEW_VERSION))

    def test_never_reconciled_is_not_proven(self):
        result = self.claim(reconciled=None)
        self.assertTrue(result["claim"].startswith("NOT PROVEN"))
        self.assertTrue(all(fr.conservative_mode(result, c) for c in cv.CHANGE_CLASSES))

    def test_a_pending_supersession_is_immediately_outside_its_window(self):
        pending = [cv.Pending("D-01", cv.SUPERSEDE_WITHDRAW, 2, "2026-09-16T09:59:59+00:00")]
        result = self.claim(pending=pending)
        self.assertFalse(result["by_change_class"][cv.SUPERSEDE_WITHDRAW]["inside_window"])
        self.assertTrue(fr.conservative_mode(result, cv.SUPERSEDE_WITHDRAW))
        self.assertFalse(fr.conservative_mode(result, cv.NEW_VERSION))

    def test_a_pending_new_version_stays_inside_its_four_hour_window(self):
        pending = [cv.Pending("D-06", cv.NEW_VERSION, 3, "2026-09-16T09:00:00+00:00")]
        result = self.claim(pending=pending)
        self.assertTrue(result["by_change_class"][cv.NEW_VERSION]["inside_window"])
        self.assertEqual(result["oldest_pending_age_seconds"], 3600)

    def test_the_reported_age_is_measured_from_when_the_change_was_noticed(self):
        """ADR-007 / FRS-008: the metric is the age of the oldest PENDING entry — measured from `noticed_at`.

        Not from when the authoritative record was written: delivery sits between those two moments, and has been
        observed to take tens of seconds. A validation run compared its own write time against this metric and read
        the difference as a measurement error, when the metric was reporting exactly what it documents.
        """
        pending = [cv.Pending("D-12", cv.NEW_VERSION, 9, "2026-09-16T09:59:00+00:00")]
        result = self.claim(pending=pending)                      # `now` is 10:00:00 in this fixture
        self.assertEqual(result["oldest_pending_age_seconds"], 60)
        self.assertEqual(result["by_change_class"][cv.NEW_VERSION]["oldest_pending_age_seconds"], 60)

    def test_operational_metrics_are_labelled_as_not_being_freshness_proof(self):
        operational = fr.operational(queue_depth=0, last_job_at="2026-09-16T09:59:00+00:00", applied_last_hour=12)
        self.assertIn("not", operational["note"])
        self.assertNotIn("global_floor", operational)


class Generations(unittest.TestCase):
    """ADR-005: a generation serves only when it is complete, and no answer mixes two versions of a document."""

    def written(self, version=3, sections=("S3", "S4")):
        return {s: {"document_id": "D-03", "section_id": s, "record_version": str(version)} for s in sections}

    def test_identifiers_carry_the_generation(self):
        self.assertEqual(gn.generation_id("D-03", 3), "D-03#g3")
        self.assertEqual(gn.custom_document_id("D-03", "S4", 3), "D-03-S4-g3")
        self.assertEqual(gn.object_key("D-03", "S4", 3), "sections/D-03/g3/S4.txt")
        self.assertEqual(gn.parse_custom_document_id("D-03-S4-g3"), ("D-03", "S4", 3))

    def test_a_complete_generation_verifies_and_may_switch(self):
        generation = gn.verify("D-03", 3, ["S3", "S4"], self.written())
        self.assertEqual(generation.state, gn.VERIFIED)
        self.assertEqual(gn.switch(generation, None).state, gn.SERVING)

    def test_a_missing_section_stops_the_switch(self):
        generation = gn.verify("D-03", 3, ["S3", "S4"], self.written(sections=("S3",)))
        self.assertEqual(generation.problem, gn.INCOMPLETE)
        with self.assertRaises(ValueError):
            gn.switch(generation, None)

    def test_content_labelled_for_another_version_never_serves(self):
        written = dict(self.written(), S4={"document_id": "D-03", "section_id": "S4", "record_version": "2"})
        self.assertEqual(gn.verify("D-03", 3, ["S3", "S4"], written).problem, gn.ATTRIBUTE_MISMATCH)

    def test_an_empty_generation_is_not_a_valid_one(self):
        self.assertEqual(gn.verify("D-03", 3, [], {}).problem, gn.EMPTY)

    # ── the promotion boundary (AB-14) ──────────────────────────────────────────────────────────────────────────
    class Serving:
        """What derived state serves right now, in the shape the ordering decision reads."""

        def __init__(self, version, status="IN_FORCE", deleted=False):
            self.version, self.status, self.deleted = version, status, deleted

    def test_a_generation_older_than_what_is_serving_never_switches(self):
        """AB-14: the invariant belongs to the TRANSITION, not to the caller that happens to be making it."""
        generation = gn.verify("D-03", 3, ["S3", "S4"], self.written())
        with self.assertRaises(gn.Regression):
            gn.switch(generation, self.Serving(5))

    def test_a_generation_newer_than_what_is_serving_switches(self):
        generation = gn.verify("D-03", 3, ["S3", "S4"], self.written())
        self.assertEqual(gn.switch(generation, self.Serving(2)).state, gn.SERVING)

    def test_re_promoting_the_same_version_stays_safe(self):
        """A rebuild at the version already serving is idempotent, not a regression."""
        generation = gn.verify("D-03", 3, ["S3", "S4"], self.written())
        self.assertEqual(gn.switch(generation, self.Serving(3), "IN_FORCE").state, gn.SERVING)

    def test_a_deleted_document_is_not_brought_back_by_an_older_generation(self):
        generation = gn.verify("D-03", 3, ["S3", "S4"], self.written())
        with self.assertRaises(gn.Regression):
            gn.switch(generation, self.Serving(4, status="DELETED", deleted=True))

    def test_switching_without_saying_what_is_being_replaced_is_impossible(self):
        """The argument is required so a future path cannot promote while forgetting the invariant exists."""
        generation = gn.verify("D-03", 3, ["S3", "S4"], self.written())
        with self.assertRaises(TypeError):
            gn.switch(generation)


class Deletion(unittest.TestCase):
    """ADR-006: deletion is an obligation over the whole derived-copy graph, not "retrieval stopped returning it"."""

    def entry(self, results):
        return dl.ledger_entry("D-12", 2, "2026-09-16T10:00:00+00:00", "2026-09-16T10:00:05+00:00", results)

    def test_the_graph_is_named_so_it_can_be_checked(self):
        self.assertEqual(sorted(dl.DERIVED_COPIES), sorted({dl.SECTION_OBJECT, dl.KNOWLEDGE_BASE_DOCUMENT,
                                                            dl.VECTOR_ENTRY, dl.GENERATION_RECORD, dl.PENDING_ENTRY}))

    def test_every_copy_proven_removed_reaches_the_physical_phase(self):
        entry = self.entry({k: (dl.DONE, None) for k in dl.DERIVED_COPIES})
        self.assertEqual((entry["phase"], dl.outstanding(entry)), (dl.PHYSICAL, []))

    def test_a_copy_that_was_never_mentioned_is_still_outstanding(self):
        entry = self.entry({dl.SECTION_OBJECT: (dl.DONE, None)})
        self.assertEqual(entry["phase"], dl.LOGICAL)
        self.assertIn(dl.VECTOR_ENTRY, dl.outstanding(entry))

    def test_one_failed_copy_keeps_the_obligation_open(self):
        results = {k: (dl.DONE if k != dl.VECTOR_ENTRY else dl.FAILED, None) for k in dl.DERIVED_COPIES}
        entry = self.entry(results)
        self.assertEqual((entry["phase"], dl.outstanding(entry)), (dl.LOGICAL, [dl.VECTOR_ENTRY]))

    def test_an_unknown_copy_kind_is_refused(self):
        with self.assertRaises(ValueError):
            self.entry({"backup_tape": (dl.DONE, None)})


class Ordering(unittest.TestCase):
    """FRS-005: late, duplicated and replayed changes never reinstate older state."""

    def reflected(self, version=3, status=rs.IN_FORCE):
        return ca.Reflected("D-06", version, status, gn.generation_id("D-06", version))

    def test_a_newer_authoritative_version_applies(self):
        self.assertEqual(ca.decide(self.reflected(), 4), ca.APPLY)

    def test_nothing_reflected_yet_applies(self):
        self.assertEqual(ca.decide(None, 1), ca.APPLY)

    def test_the_same_version_again_is_a_duplicate(self):
        self.assertEqual(ca.decide(self.reflected(), 3), ca.DUPLICATE)

    def test_a_replayed_older_version_is_refused(self):
        self.assertEqual(ca.decide(self.reflected(), 2), ca.OLDER)

    def test_a_status_change_at_the_same_version_still_applies(self):
        """Supersession in place does not bump the version; treating it as a duplicate would never converge."""
        self.assertEqual(ca.decide(self.reflected(), 3, rs.SUPERSEDED), ca.APPLY)

    def test_a_late_or_replayed_change_never_reinstates_a_deleted_document(self):
        """FRS-005: the ordering rule. Anything not newer than what was deleted is refused."""
        self.assertEqual(ca.decide(self.reflected(status=rs.DELETED), 2), ca.AFTER_DELETE)
        self.assertEqual(ca.decide(self.reflected(status=rs.DELETED), 3), ca.AFTER_DELETE)

    def test_a_new_authoritative_record_brings_a_deleted_document_back(self):
        """ADR-004 clause 4, second half: only a new authoritative record may — and a newer version is exactly that.

        Without this, a document superseded and then reinstated by its owner could never return, and reconciliation
        would request a repair for ever that could never be applied.
        """
        self.assertEqual(ca.decide(self.reflected(status=rs.DELETED), 4), ca.APPLY)

    def test_the_incoming_version_must_come_from_the_authoritative_record(self):
        for bad in (0, -1, "3", True, None):
            with self.assertRaises(ValueError):
                ca.decide(self.reflected(), bad)


if __name__ == "__main__":
    unittest.main()
