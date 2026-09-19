"""FRS-004 retry accounting and window-breach escalation — and the clock that used to reset underneath them.

    A PENDING ENTRY'S `noticed_at` IS THE MOMENT THE CHANGE WAS FIRST NOTICED.

Reconciliation wrote `started_at` into every repair it requested, on every pass. A change that had been diverging for
hours therefore looked, each hour, as though it had just been noticed: `oldest_pending_age_seconds` fell back to 0,
no change class could ever leave its window, and no breach could ever be raised. The system reported healthy
reconciliation and a fresh pending set while an unrepairable change sat there indefinitely — silent loss of exactly
the kind FRS-004 exists to prevent, produced by the mechanism meant to detect it.

Three separate things are pinned here, because they fail independently:

    the clock          a repeated pass must not restamp an entry it did not newly notice
    the accounting     `attempts` counts GENUINE repair invocations, never observations of divergence
    the escalation     the alert is RAISED first and the entry marked second, never the other way round

Everything runs against in-memory fakes: no AWS account, no network.
"""
import unittest
from datetime import datetime, timezone

import support  # noqa: F401 — puts app/ on the import path
from adapters import stores
from change import applier, reconciler
from core import audit_record as ar, convergence as cv, freshness as fr, record_state as rs

KB = {"shared": ("kb-shared", "ds-shared"), "restricted": ("kb-restricted", "ds-restricted")}
TARGET = "D-06"


def moment(hour, minute=0):
    return f"2026-09-16T{hour:02d}:{minute:02d}:00+00:00"


def parsed(hour, minute=0):
    return datetime(2026, 9, 16, hour, minute, 0, tzinfo=timezone.utc)


class ReconcilerHarness(unittest.TestCase):
    """A divergence that persists: authority at v4, derived state stuck at v3, pass after pass."""

    def setUp(self):
        self.store = support.FakeConvergence()
        self.records = support.FakeRecords({TARGET: support.lifecycle(TARGET, version=4)})
        self.store.put_reflected(TARGET, 3, rs.IN_FORCE, f"{TARGET}#g3")
        self.emitted = []

    def emitter(self, *, fail=False, watcher=None):
        def emit(deployment, total, breaches):
            if watcher is not None:
                watcher()
            if fail:
                raise RuntimeError("Throttling")
            self.emitted.append({"deployment": deployment, "total": total, "breaches": breaches})
        return emit

    def reconcile(self, now, emit=None, records=None):
        return reconciler.run({"run_id": f"rec-{now}"}, records or self.records, self.store,
                              applier="applier-function", invoke=lambda _n, _i: None,
                              deployment="tla-s01e03-normal", now=now, emit=emit)


class ThePendingClockDoesNotReset(ReconcilerHarness):
    """The defect itself. Each of these fails against the pre-fix reconciler."""

    def test_repeated_passes_keep_the_moment_the_change_was_first_noticed(self):
        for hour in (10, 11, 12):
            self.reconcile(moment(hour))
        self.assertEqual(self.store.pending[TARGET].noticed_at, moment(10))

    def test_the_reported_age_grows_across_passes_instead_of_returning_to_zero(self):
        """The consequence that matters: this number is what a window breach is decided from."""
        for hour in (10, 11, 12):
            self.reconcile(moment(hour))
        claim = fr.claim({}, self.store.pending, now=parsed(15), last_reconciliation=moment(12))
        self.assertEqual(claim["oldest_pending_age_seconds"], 5 * 3600)      # five hours, against a four-hour window
        self.assertFalse(claim["by_change_class"][cv.NEW_VERSION]["inside_window"])

    def test_a_change_that_converged_and_diverged_again_is_noticed_afresh(self):
        """The fix must preserve the clock, not freeze it: a NEW divergence is a new observation."""
        self.reconcile(moment(10))
        self.store.clear_pending(TARGET)                      # it converged
        self.reconcile(moment(14))                            # and diverged again
        self.assertEqual(self.store.pending[TARGET].noticed_at, moment(14))

    def test_a_document_already_pending_from_delivery_is_not_restamped(self):
        """Delivery noticed it first. Reconciliation finding the same divergence must not reset its age."""
        self.store.put_pending(cv.Pending(TARGET, cv.NEW_VERSION, 4, moment(9), detail="CHANGE_NOTIFIED"))
        self.reconcile(moment(10))
        self.assertEqual(self.store.pending[TARGET].noticed_at, moment(9))

    def test_the_entry_is_still_marked_as_reconciliation_drift(self):
        """Preserving the clock must not quietly change what the entry says it is."""
        self.reconcile(moment(10))
        self.assertEqual(self.store.pending[TARGET].detail, "RECONCILIATION_DRIFT")


class AWindowBreachIsDetectedAndEscalated(ReconcilerHarness):
    """FRS-004 / OPS-001 / ADR-007 §3."""

    def test_a_change_inside_its_window_is_not_escalated(self):
        self.reconcile(moment(10), emit=self.emitter())
        summary = self.reconcile(moment(11), emit=self.emitter())
        self.assertEqual(summary["escalation"]["breaches"], {})
        self.assertEqual(summary["escalation"]["newly_escalated"], [])
        self.assertIsNone(self.store.pending[TARGET].escalated_at)

    def test_a_change_past_its_window_is_escalated(self):
        self.reconcile(moment(10), emit=self.emitter())
        summary = self.reconcile(moment(16), emit=self.emitter())        # new_version window is four hours
        self.assertEqual(summary["escalation"]["breaches"], {cv.NEW_VERSION: [TARGET]})
        self.assertEqual(summary["escalation"]["newly_escalated"], [TARGET])
        self.assertEqual(self.store.pending[TARGET].escalated_at, moment(16))    # the pass's time, not wall clock

    def test_an_already_escalated_change_is_not_escalated_twice_but_still_counts(self):
        """The alarm must stay on while the breach lasts; the transition must happen once."""
        self.reconcile(moment(10), emit=self.emitter())
        first = self.reconcile(moment(16), emit=self.emitter())
        second = self.reconcile(moment(17), emit=self.emitter())
        self.assertEqual(first["escalation"]["newly_escalated"], [TARGET])
        self.assertEqual(second["escalation"]["newly_escalated"], [])
        self.assertEqual(second["escalation"]["breached_total"], 1)
        self.assertEqual(self.store.pending[TARGET].escalated_at, moment(16))

    def test_the_alert_names_the_class_and_the_affected_identifiers(self):
        """OPS-001 is specific: naming the class alone, or the count alone, does not discharge it."""
        self.reconcile(moment(10), emit=self.emitter())
        self.reconcile(moment(16), emit=self.emitter())
        self.assertEqual(self.emitted[-1]["breaches"], {cv.NEW_VERSION: [TARGET]})

    def test_a_safety_critical_class_breaches_as_soon_as_it_is_pending(self):
        """supersede_withdraw has a zero-second window: there is no acceptable pending period."""
        self.store.put_pending(cv.Pending("D-01", cv.SUPERSEDE_WITHDRAW, 2, moment(10), detail="CHANGE_NOTIFIED"))
        summary = self.reconcile(moment(10, 1), emit=self.emitter())
        self.assertEqual(summary["escalation"]["breaches"], {cv.SUPERSEDE_WITHDRAW: ["D-01"]})

    def test_the_metric_is_emitted_on_every_completed_pass_including_zero(self):
        """Without a zero the alarm would latch on for ever once it had fired."""
        self.reconcile(moment(10), emit=self.emitter())
        self.assertEqual(self.emitted[-1]["total"], 0)
        self.assertTrue(self.emitted[-1]["deployment"])


class TheAlertIsRaisedBeforeItIsRecorded(ReconcilerHarness):
    """Order is load-bearing, not stylistic."""

    def test_the_metric_is_emitted_before_escalated_at_is_persisted(self):
        seen = {}

        def watcher():
            seen["escalated_at_at_emit_time"] = self.store.pending[TARGET].escalated_at

        self.reconcile(moment(10), emit=self.emitter())
        self.reconcile(moment(16), emit=self.emitter(watcher=watcher))
        self.assertIn("escalated_at_at_emit_time", seen)
        self.assertIsNone(seen["escalated_at_at_emit_time"])
        self.assertIsNotNone(self.store.pending[TARGET].escalated_at)

    def test_an_alert_that_was_never_raised_marks_nothing_as_escalated(self):
        self.reconcile(moment(10), emit=self.emitter())
        summary = self.reconcile(moment(16), emit=self.emitter(fail=True))
        self.assertFalse(summary["escalation"]["emitted"])
        self.assertEqual(summary["escalation"]["emit_error"]["error"], "RuntimeError")
        self.assertIsNone(self.store.pending[TARGET].escalated_at)

    def test_the_breach_is_escalated_again_on_the_next_pass_after_a_failed_emit(self):
        """Persisting first would have silenced this breach permanently."""
        self.reconcile(moment(10), emit=self.emitter())
        self.reconcile(moment(16), emit=self.emitter(fail=True))
        recovered = self.reconcile(moment(17), emit=self.emitter())
        self.assertEqual(recovered["escalation"]["newly_escalated"], [TARGET])
        self.assertTrue(recovered["escalation"]["emitted"])

    def test_a_failed_emit_does_not_fail_the_reconciliation_pass(self):
        """The pass genuinely completed. Losing the alert must not also lose the completeness it proved."""
        summary = self.reconcile(moment(16), emit=self.emitter(fail=True))
        self.assertIsNotNone(summary["completed_at"])
        self.assertEqual(sorted(summary["advanced"]), sorted(cv.CHANGE_CLASSES))


class AttemptsCountGenuineInvocations(unittest.TestCase):
    """`attempts` is evidence that something was TRIED, not that something was SEEN."""

    def setUp(self):
        self.store = support.FakeConvergence()
        self.storage = support.FakeStorage()
        self.source = support.FakeSource({})          # no source document: every apply of D-06 fails
        self.agent = support.FakeAgent()
        self.records = support.FakeRecords({TARGET: support.lifecycle(TARGET, version=1)})

    def apply(self, store=None):
        return applier.run({"document_ids": [TARGET]}, self.records, self.source, self.storage, store or self.store,
                           self.agent, KB, "tla-s01e03-normal", sleep=lambda _s: None)

    def test_a_failed_apply_records_one_attempt(self):
        self.store.put_pending(cv.Pending(TARGET, cv.NEW_VERSION, 1, moment(10)))
        report = self.apply()
        self.assertEqual([f["document_id"] for f in report["failed"]], [TARGET])
        self.assertEqual(self.store.pending[TARGET].attempts, 1)
        self.assertTrue(self.store.pending[TARGET].last_attempt_at)

    def test_repeated_failures_accumulate(self):
        self.store.put_pending(cv.Pending(TARGET, cv.NEW_VERSION, 1, moment(10)))
        self.apply()
        self.apply()
        self.assertEqual(self.store.pending[TARGET].attempts, 2)

    def test_a_cleared_entry_is_never_resurrected_by_attempt_accounting(self):
        """A document that converged must not reappear as pending and later escalate as a stuck change."""
        self.store.record_attempt(TARGET, moment(11))
        self.assertEqual(self.store.pending, {})

    def test_the_real_store_guards_attempt_accounting_with_a_condition(self):
        """The fake above proves only that the fake behaves. This pins the PRODUCTION guard.

        `attribute_exists(pk)` is what stops a concurrent clear_pending from being undone by an in-flight attempt
        count. A test that asserted this against the fixture alone would supply the very fact it is meant to check.
        """
        calls = []

        class OnlyUpdate:
            def update_item(self, **kwargs):
                calls.append(kwargs)

        stores.ConvergenceStore(OnlyUpdate(), "table").record_attempt(TARGET, moment(11))
        self.assertEqual(calls[0]["ConditionExpression"], "attribute_exists(pk)")
        self.assertIn("ADD", calls[0]["UpdateExpression"])
        self.assertEqual(calls[0]["Key"], {"pk": {"S": f"PENDING#{TARGET}"}})

    def test_attempt_accounting_never_masks_the_failure_it_counts(self):
        class Hostile(support.FakeConvergence):
            def record_attempt(self, document_id, at):
                raise RuntimeError("ProvisionedThroughputExceeded")

        store = Hostile()
        store.put_pending(cv.Pending(TARGET, cv.NEW_VERSION, 1, moment(10)))
        report = self.apply(store=store)
        self.assertEqual([f["document_id"] for f in report["failed"]], [TARGET])
        self.assertEqual(report["failed"][0]["attempt_accounting"], "RuntimeError")

    def test_reconciliation_does_not_count_an_attempt_it_merely_requested(self):
        """It invokes the applier with InvocationType="Event" and never learns the outcome."""
        store = support.FakeConvergence()
        records = support.FakeRecords({TARGET: support.lifecycle(TARGET, version=4)})
        store.put_reflected(TARGET, 3, rs.IN_FORCE, f"{TARGET}#g3")
        for hour in (10, 11):
            reconciler.run({"run_id": f"rec-{hour}"}, records, store, applier="applier-function",
                           invoke=lambda _n, _i: None, deployment="d", now=moment(hour))
        self.assertEqual(store.pending[TARGET].attempts, 0)

    def test_reconciliation_carries_accounting_forward_rather_than_zeroing_it(self):
        store = support.FakeConvergence()
        records = support.FakeRecords({TARGET: support.lifecycle(TARGET, version=4)})
        store.put_reflected(TARGET, 3, rs.IN_FORCE, f"{TARGET}#g3")
        reconciler.run({"run_id": "r1"}, records, store, applier="a", invoke=lambda _n, _i: None,
                       deployment="d", now=moment(10))
        store.record_attempt(TARGET, moment(10, 30))
        reconciler.run({"run_id": "r2"}, records, store, applier="a", invoke=lambda _n, _i: None,
                       deployment="d", now=moment(11))
        self.assertEqual(store.pending[TARGET].attempts, 1)
        self.assertEqual(store.pending[TARGET].last_attempt_at, moment(10, 30))


class TheRequestPathRecordIsUnchanged(unittest.TestCase):
    """The accounting is change-path state. Putting it in the audit record would break every pending request."""

    def entry(self):
        return cv.Pending(TARGET, cv.NEW_VERSION, 2, moment(10), detail="RECONCILIATION_DRIFT",
                          attempts=3, last_attempt_at=moment(11), escalated_at=moment(12))

    def test_the_audit_projection_is_exactly_what_the_schema_allows(self):
        self.assertEqual(set(self.entry().item()), set(ar.PENDING))

    def test_the_audit_record_still_validates_with_a_pending_entry(self):
        record = ar.new("req-1", "tla-s01e03-normal", "normal")
        record["convergence"]["pending"] = [self.entry().item()]
        self.assertIs(ar.validate(record), record)

    def test_the_stored_projection_would_be_refused_by_the_audit_schema(self):
        """Why the two projections are separate: this is what widening item() would have done on AWS, not locally."""
        record = ar.new("req-1", "tla-s01e03-normal", "normal")
        record["convergence"]["pending"] = [self.entry().stored()]
        with self.assertRaises(ar.AuditSchemaError):
            ar.validate(record)

    def test_an_entry_written_before_this_change_still_loads(self):
        """Pending rows already in the table carry none of these attributes. No migration is performed."""
        entry = cv.Pending(TARGET, cv.NEW_VERSION, 2, moment(10))
        self.assertEqual((entry.attempts, entry.last_attempt_at, entry.escalated_at), (0, None, None))


if __name__ == "__main__":
    unittest.main()
