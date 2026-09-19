"""The pending INCIDENT and its class: fixed when the incident is created, preserved until it converges.

    RECONCILIATION OBSERVES A DIFFERENCE. IT NEVER OBSERVES THE EVENT THAT CAUSED ONE.

It holds no "before" record and no labels, so `change_class_for(None, state)` can only ever return deletion,
supersede_withdraw or new_version — a reclassification is structurally unreachable from reconciliation. The repair
loop nonetheless overwrote the class on every pass, so a `reclassify_up` incident (safety-critical, zero-second
window) silently became `new_version` (not safety-critical, four hours).

That is not only an alerting defect. `conservative_mode` consults SAFETY_CRITICAL_CLASSES only, so the downgrade
moved the request path from WITHHOLDING to SERVING — which is why this is pinned here rather than treated as
observability. The correction needs no severity ordering: the class is set on CREATION and preserved thereafter.

Everything runs against in-memory fakes: no AWS account, no network, no backdated timestamps.
"""
import json
import unittest

import support  # noqa: F401 — puts app/ on the import path
from change import applier, notifier, reconciler
from core import convergence as cv, eligibility, freshness as fr, record_state as rs, verification as vf

KB = {"shared": ("kb-shared", "ds-shared"), "restricted": ("kb-restricted", "ds-restricted")}
TARGET = "D-04"
SOURCE = "# T\n\n## §1 S\n\nbody text.\n"
NOTICED = "2026-09-16T10:00:00+00:00"


def record(label="INTERNAL", scope=None, version=1, status=rs.IN_FORCE, **extra):
    base = {"document_id": TARGET, "document_label": label, "document_scope": scope, "version": version,
            "status": status, "title": "T",
            "sections": [{"section_id": "S1", "title": "S", "special_category": False, "label": None, "scope": None}]}
    base.update(extra)
    return base


def stream(new=None, old=None):
    image = {"Keys": {"document_id": {"S": TARGET}}}
    if new is not None:
        image["NewImage"] = {"document_id": {"S": TARGET}, "record": {"S": json.dumps(new)}}
    if old is not None:
        image["OldImage"] = {"document_id": {"S": TARGET}, "record": {"S": json.dumps(old)}}
    return {"dynamodb": image}


class Obstructed:
    """The build-blocking mechanism: the source object is gone, so the build cannot complete."""

    def read(self, document_id):
        raise RuntimeError("NoSuchKey")


class Harness(unittest.TestCase):
    def setUp(self):
        self.store = support.FakeConvergence()
        self.storage, self.agent = support.FakeStorage(), support.FakeAgent()
        self.records = support.FakeRecords({TARGET: record()})
        self.live = support.FakeSource({TARGET: SOURCE})
        self.emitted = []
        applier.run({"document_ids": [TARGET]}, self.records, self.live, self.storage, self.store, self.agent, KB,
                    "n", sleep=lambda _s: None)

    def obstructed_apply(self, document_ids):
        applier.run({"document_ids": sorted(document_ids)}, self.records, Obstructed(), self.storage, self.store,
                    self.agent, KB, "n", sleep=lambda _s: None)

    def raise_incident(self, new=None, old=None, now=NOTICED):
        """A real upward reclassification, delivered and then failing to apply because the source is gone."""
        new = new or record("CONFIDENTIAL", "SEC-SIGNALLING", 2)
        self.records.records[TARGET] = new
        notifier.run({"Records": [stream(new=new, old=old or record())]}, self.store, applier="a",
                     invoke=lambda _n, ids: self.obstructed_apply(ids), now=now)
        return self.store.pending[TARGET]

    def reconcile(self, now, emit=None, records=None):
        return reconciler.run({"run_id": f"rec-{now}"}, records or self.records, self.store, applier="a",
                              invoke=lambda _n, ids: self.obstructed_apply(ids), deployment="tla-s01e03-normal",
                              now=now, emit=emit if emit is not None else self.recorder())

    def recorder(self):
        def emit(deployment, total, breaches):
            self.emitted.append({"deployment": deployment, "total": total, "breaches": breaches})
        return emit


class TheIncidentClassSurvivesReconciliation(Harness):
    """The defect, and its exact consequence."""

    def test_a_zero_window_incident_is_not_downgraded_by_a_less_informed_observation(self):
        before = self.raise_incident()
        self.assertEqual(before.change_class, cv.RECLASSIFY_UP)
        summary = self.reconcile("2026-09-16T10:00:30+00:00")
        after = self.store.pending[TARGET]
        self.assertEqual([d["document_id"] for d in summary["divergent"]], [TARGET])
        self.assertEqual(after.change_class, cv.RECLASSIFY_UP, "reconciliation must not reclassify the incident")
        self.assertEqual(fr.WINDOW_SECONDS[after.change_class], 0)

    def test_reconciliation_cannot_produce_a_reclassification_at_all(self):
        """Why preserving needs no severity ordering: the observed class space excludes both reclassifications."""
        observed = {cv.change_class_for(None, rs.RecordState(TARGET, 1, status))
                    for status in (rs.IN_FORCE, rs.SUPERSEDED, rs.WITHDRAWN, rs.DELETED)} | {cv.DELETION}
        self.assertEqual(observed, {cv.NEW_VERSION, cv.SUPERSEDE_WITHDRAW, cv.DELETION})
        self.assertNotIn(cv.RECLASSIFY_UP, observed)
        self.assertNotIn(cv.RECLASSIFY_DOWN, observed)

    def test_the_downgrade_would_have_moved_the_request_path_from_withholding_to_serving(self):
        """The safety consequence, measured rather than asserted."""
        marks = {c: cv.Watermark(c, NOTICED, "r", NOTICED, 15) for c in cv.CHANGE_CLASSES}
        from datetime import datetime, timezone
        now = datetime(2026, 9, 16, 10, 5, 0, tzinfo=timezone.utc)
        outcomes = {}
        for klass in (cv.RECLASSIFY_UP, cv.NEW_VERSION):
            claim = fr.claim(marks, {TARGET: cv.Pending(TARGET, klass, 2, NOTICED)}, now=now,
                             last_reconciliation=NOTICED)
            outcomes[klass] = any(fr.conservative_mode(claim, c) for c in cv.SAFETY_CRITICAL_CLASSES)
        self.assertTrue(outcomes[cv.RECLASSIFY_UP], "a breached safety-critical incident must withhold")
        self.assertFalse(outcomes[cv.NEW_VERSION], "the downgraded class is not even consulted")

    def test_the_incident_still_escalates_after_a_reconciliation_pass(self):
        self.raise_incident()
        summary = self.reconcile("2026-09-16T10:00:30+00:00")
        escalation = summary["escalation"]
        self.assertEqual(escalation["breaches"], {cv.RECLASSIFY_UP: [TARGET]})
        self.assertEqual(escalation["newly_escalated"], [TARGET])
        self.assertTrue(escalation["emitted"])
        self.assertEqual(self.store.pending[TARGET].escalated_at, "2026-09-16T10:00:30+00:00")

    def test_the_alert_names_the_class_and_the_identifier(self):
        """OPS-001 is specific about both."""
        self.raise_incident()
        self.reconcile("2026-09-16T10:00:30+00:00")
        self.assertEqual(self.emitted[-1]["breaches"], {cv.RECLASSIFY_UP: [TARGET]})
        self.assertEqual(self.emitted[-1]["total"], 1)


class TheIncidentLifecycle(Harness):
    """Creation, preservation, convergence, recurrence."""

    def test_first_noticed_at_is_preserved_across_passes(self):
        self.raise_incident()
        for minute in (1, 2, 3):
            self.reconcile(f"2026-09-16T10:0{minute}:00+00:00")
        self.assertEqual(self.store.pending[TARGET].noticed_at, NOTICED)

    def test_attempts_remain_real_applier_invocations_not_observations(self):
        self.raise_incident()
        first = self.store.pending[TARGET].attempts
        self.reconcile("2026-09-16T10:00:30+00:00")
        self.assertGreater(self.store.pending[TARGET].attempts, first)
        self.assertTrue(self.store.pending[TARGET].last_attempt_at)

    def test_convergence_clears_the_incident(self):
        self.raise_incident()
        self.reconcile("2026-09-16T10:00:30+00:00")
        self.records.records[TARGET] = record("CONFIDENTIAL", "SEC-SIGNALLING", 3)
        applier.run({"document_ids": [TARGET]}, self.records, self.live, self.storage, self.store, self.agent, KB,
                    "n", sleep=lambda _s: None)
        self.assertEqual(dict(self.store.pending), {})

    def test_a_recurrence_after_convergence_is_a_new_incident(self):
        self.raise_incident()
        self.records.records[TARGET] = record("CONFIDENTIAL", "SEC-SIGNALLING", 3)
        applier.run({"document_ids": [TARGET]}, self.records, self.live, self.storage, self.store, self.agent, KB,
                    "n", sleep=lambda _s: None)
        self.assertEqual(dict(self.store.pending), {})

        # ONE record set drives both the pass and the repair. Handing the reconciler a different set from the applier
        # made the applier read the older version, call it DUPLICATE and clear pending — the CASE C mechanism,
        # reproduced by a fixture inconsistency rather than by the architecture.
        self.records.records[TARGET] = record("CONFIDENTIAL", "SEC-SIGNALLING", 4)
        summary = reconciler.run({"run_id": "recurrence"}, self.records, self.store, applier="a",
                                 invoke=lambda _n, _i: None, deployment="tla-s01e03-normal",
                                 now="2026-09-16T11:00:00+00:00", emit=self.recorder())
        fresh = self.store.pending[TARGET]
        self.assertEqual([d["document_id"] for d in summary["divergent"]], [TARGET])
        self.assertEqual(fresh.noticed_at, "2026-09-16T11:00:00+00:00", "a recurrence is a NEW incident")
        self.assertEqual(fresh.change_class, cv.NEW_VERSION, "classified afresh, not inherited from the old incident")
        self.assertIsNone(fresh.escalated_at)
        self.assertEqual(fresh.attempts, 0, "accounting starts again")

    def test_a_genuine_later_event_still_upgrades_through_the_notifier(self):
        """Reconciliation never upgrades; the notifier, which sees the event, does."""
        self.raise_incident()
        self.assertEqual(self.store.pending[TARGET].change_class, cv.RECLASSIFY_UP)
        superseded = record("CONFIDENTIAL", "SEC-SIGNALLING", 3, status=rs.SUPERSEDED, superseded_by="D-03")
        self.records.records[TARGET] = superseded
        notifier.run({"Records": [stream(new=superseded, old=record("CONFIDENTIAL", "SEC-SIGNALLING", 2))]},
                     self.store, applier=None, invoke=None, now="2026-09-16T10:02:00+00:00")
        self.assertEqual(self.store.pending[TARGET].change_class, cv.SUPERSEDE_WITHDRAW)


class NothingElseMayClearTheIncident(Harness):
    def test_watermark_advancement_does_not_clear_it(self):
        self.raise_incident()
        summary = self.reconcile("2026-09-16T10:00:30+00:00")
        self.assertEqual(sorted(summary["advanced"]), sorted(cv.CHANGE_CLASSES))
        self.assertIn(TARGET, self.store.pending)
        self.assertEqual(self.store.pending[TARGET].change_class, cv.RECLASSIFY_UP)

    def test_a_zero_document_pass_cannot_clear_it(self):
        self.raise_incident()
        empty = support.FakeRecords({})
        summary = reconciler.run({"run_id": "empty"}, empty, self.store, applier="a",
                                 invoke=lambda _n, ids: self.obstructed_apply(ids), deployment="d",
                                 now="2026-09-16T10:00:30+00:00", emit=self.recorder())
        self.assertIn(TARGET, self.store.pending)
        self.assertEqual(self.store.pending[TARGET].change_class, cv.RECLASSIFY_UP)
        self.assertEqual(summary["escalation"]["breaches"], {cv.RECLASSIFY_UP: [TARGET]})


class EscalationRemainsCorrect(Harness):
    def test_escalation_emits_once_and_deduplicates(self):
        self.raise_incident()
        first = self.reconcile("2026-09-16T10:00:30+00:00")
        second = self.reconcile("2026-09-16T10:01:00+00:00")
        self.assertEqual(first["escalation"]["newly_escalated"], [TARGET])
        self.assertEqual(second["escalation"]["newly_escalated"], [])
        self.assertEqual(second["escalation"]["breached_total"], 1)

    def test_an_emission_failure_marks_nothing_and_stays_retryable(self):
        self.raise_incident()

        def failing(_deployment, _total, _breaches):
            raise RuntimeError("Throttling")

        failed = self.reconcile("2026-09-16T10:00:30+00:00", emit=failing)
        self.assertFalse(failed["escalation"]["emitted"])
        self.assertIsNone(self.store.pending[TARGET].escalated_at)
        recovered = self.reconcile("2026-09-16T10:01:00+00:00")
        self.assertEqual(recovered["escalation"]["newly_escalated"], [TARGET])
        self.assertTrue(recovered["escalation"]["emitted"])


class RepairBehaviourIsUnchanged(Harness):
    def test_the_repair_still_runs_and_still_uses_authority_not_the_incident_class(self):
        """`pending.change_class` has exactly one consumer: freshness/escalation. Repair reads authority."""
        self.raise_incident()
        self.reconcile("2026-09-16T10:00:30+00:00")
        self.records.records[TARGET] = record("CONFIDENTIAL", "SEC-SIGNALLING", 3)
        report = applier.run({"document_ids": [TARGET]}, self.records, self.live, self.storage, self.store,
                             self.agent, KB, "n", sleep=lambda _s: None)
        self.assertEqual([a["document_id"] for a in report["applied"]], [TARGET])
        self.assertEqual(self.store.reflected_items[TARGET].version, 3)

    def test_a_deletion_incident_still_takes_the_removal_path_and_discharges_the_pending_entry(self):
        """ADR-006: the pending entry is itself one of DERIVED_COPIES, so removal clears it by design."""
        from core import deletion as dl
        self.assertIn(dl.PENDING_ENTRY, dl.DERIVED_COPIES)
        self.records.records[TARGET] = record(status=rs.SUPERSEDED, version=2, superseded_by="D-03")
        report = applier.run({"document_ids": [TARGET]}, self.records, self.live, self.storage, self.store,
                             self.agent, KB, "n", sleep=lambda _s: None)
        self.assertEqual([d["document_id"] for d in report["deleted"]], [TARGET])
        self.assertEqual(dict(self.store.pending), {})


class LabelDriftRemainsExposed(unittest.TestCase):
    """DEFECT 2, deliberately NOT repaired here. Recorded so it cannot change silently."""

    def test_a_label_only_change_is_invisible_to_reconciliation(self):
        store = support.FakeConvergence()
        records = support.FakeRecords({TARGET: record("CONFIDENTIAL", "SEC-SIGNALLING", 1)})
        store.put_reflected(TARGET, 1, rs.IN_FORCE, f"{TARGET}#g1")
        missing, extra, divergent = reconciler.compare(records.export(), store.reflected_all())
        self.assertEqual(([m[0] for m in missing], [e[0] for e in extra], [d[0] for d in divergent]), ([], [], []))

    def test_derived_state_structurally_cannot_hold_a_label(self):
        """`compare()` is not forgetting to check: the reflected row has no label to check against."""
        from core.change_apply import Reflected
        self.assertEqual(sorted(Reflected.__dataclass_fields__),
                         ["document_id", "generation_id", "status", "version"])

    def test_sec_002_still_holds_at_the_answer_boundary(self):
        """The stale chunk crosses the RETRIEVAL boundary; verification refuses it against fresh authority."""
        stale = vf.RetrievedChunk(f"{TARGET}-S1-g1", "shared", TARGET, "S1", "INTERNAL", "NONE", "1", 0.9, "body")
        requester = eligibility.allow("sub-1", domains=[], cases=[], hr_version=1, grants_version=1)
        result = vf.verify(requester, [stale], {TARGET: record("CONFIDENTIAL", "SEC-SIGNALLING", 1)})
        self.assertEqual(result.status, vf.MISMATCH)
        self.assertEqual(result.verified, ())
        self.assertEqual([reason for _chunk, reason in result.mismatches], ["LABEL_MISMATCH"])


if __name__ == "__main__":
    unittest.main()
