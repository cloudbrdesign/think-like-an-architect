"""The change path: notification, application, reconciliation — and the boundaries between them.

    THE NOTIFIER SAYS "SOMETHING CHANGED".        It may never say "everything is accounted for".
    THE APPLIER MAKES DERIVED STATE MATCH.        It may never apply an older change over a newer one.
    RECONCILIATION SAYS WHAT IS ACCOUNTED FOR.    Only a completed pass may advance a watermark.

Everything here runs against in-memory fakes: no AWS account, no network.
"""
import json
import unittest

import support
from change import applier, notifier, reconciler
from core import change_apply as ca, convergence as cv, deletion as dl, generations as gn, record_state as rs

KB = {"shared": ("kb-shared", "ds-shared"), "restricted": ("kb-restricted", "ds-restricted")}


def stream(document_id, new=None, old=None):
    """One DynamoDB stream record for the authoritative records table."""
    image = {"Keys": {"document_id": {"S": document_id}}}
    if new is not None:
        image["NewImage"] = {"document_id": {"S": document_id}, "record": {"S": json.dumps(new)}}
    if old is not None:
        image["OldImage"] = {"document_id": {"S": document_id}, "record": {"S": json.dumps(old)}}
    return {"dynamodb": image}


def event(*records):
    return {"Records": list(records)}


class Notifier(unittest.TestCase):
    def notify(self, *stream_records):
        store = support.FakeConvergence()
        report = notifier.run(event(*stream_records), store, now="2026-09-16T10:00:00+00:00")
        return store, report

    def test_a_change_is_pending_before_any_content_work_starts(self):
        store, report = self.notify(stream("D-06", new=support.lifecycle("D-06", version=3),
                                           old=support.lifecycle("D-06", version=2)))
        self.assertEqual(sorted(store.pending), ["D-06"])
        self.assertEqual(store.pending["D-06"].change_class, cv.NEW_VERSION)
        self.assertEqual(report["pending"][0]["effective_version"], 3)

    def test_a_notification_never_advances_a_watermark(self):
        """§7 and ADR-003: delivery tells us about changes we received, never about changes we never saw."""
        store, _ = self.notify(stream("D-01", new=support.lifecycle("D-01", status=rs.WITHDRAWN)))
        self.assertEqual(store.advances, [])
        self.assertEqual(store.watermarks, {})

    def test_supersession_is_classified_as_safety_critical(self):
        store, _ = self.notify(stream("D-01", new=support.lifecycle("D-01", status=rs.SUPERSEDED,
                                                                    superseded_by="D-06"),
                                      old=support.lifecycle("D-01")))
        self.assertIn(store.pending["D-01"].change_class, cv.SAFETY_CRITICAL_CLASSES)

    def test_upward_reclassification_is_classified_from_the_labels(self):
        store, _ = self.notify(stream("D-13", new=support.lifecycle("D-13", document_label="CONFIDENTIAL"),
                                      old=support.lifecycle("D-13", document_label="INTERNAL")))
        self.assertEqual(store.pending["D-13"].change_class, cv.RECLASSIFY_UP)

    def test_a_removed_record_is_a_deletion(self):
        store, _ = self.notify(stream("D-12", old=support.lifecycle("D-12")))
        self.assertEqual(store.pending["D-12"].change_class, cv.DELETION)

    def test_history_items_are_not_changes_in_their_own_right(self):
        store, _ = self.notify(stream("HISTORY#D-06#v2", new=support.lifecycle("D-06", version=2)))
        self.assertEqual(store.pending, {})

    def test_the_applier_is_asked_to_converge_the_documents_that_changed(self):
        store, asked = support.FakeConvergence(), []
        notifier.run(event(stream("D-06", new=support.lifecycle("D-06", version=3))), store,
                     applier="applier-function", invoke=lambda name, ids: asked.append((name, sorted(ids))))
        self.assertEqual(asked, [("applier-function", ["D-06"])])


class Applier(unittest.TestCase):
    """Ordering and deletion. The build path is exercised end to end by the harness against a real knowledge base."""

    def setUp(self):
        self.store = support.FakeConvergence()
        self.storage, self.agent = support.FakeStorage(), support.FakeAgent()
        self.source = support.FakeSource({"D-03": "# t\n\n## §1 A\n\nbody\n"})

    def apply(self, document_id, record):
        records = support.FakeRecords({document_id: record} if record is not None else {})
        return applier.apply_one(document_id, record, records, self.source, self.storage, self.store, self.agent, KB,
                                 sleep=lambda _s: None, now="2026-09-16T10:00:00+00:00")

    def serving(self, document_id="D-03", version=2, sections=("S3", "S4"), tier="shared"):
        """Put a serving generation in place, with its derived copies, without running a build."""
        self.store.put_generation(gn.Generation(document_id, version, gn.SERVING, tuple(sections)))
        self.store.put_reflected(document_id, version, rs.IN_FORCE, gn.generation_id(document_id, version))
        for section_id in sections:
            self.storage.put(tier, gn.object_key(document_id, section_id, version), "body")
            self.agent.documents[(KB[tier][0], gn.custom_document_id(document_id, section_id, version))] = "INDEXED"

    def test_a_replayed_older_version_is_recorded_as_refused_not_applied(self):
        self.serving(version=3)
        outcome = self.apply("D-03", support.lifecycle("D-03", version=2))
        self.assertEqual((outcome["bucket"], outcome["decision"]), ("skipped", ca.OLDER))
        self.assertEqual(self.store.reflected("D-03").version, 3)

    def test_a_duplicate_of_a_change_already_applied_clears_the_pending_entry(self):
        self.serving(version=3)
        self.store.put_pending(cv.Pending("D-03", cv.NEW_VERSION, 3, "2026-09-16T10:00:00+00:00"))
        outcome = self.apply("D-03", support.lifecycle("D-03", version=3))
        self.assertEqual((outcome["bucket"], outcome["decision"]), ("skipped", ca.DUPLICATE))
        self.assertEqual(self.store.pending, {})

    def test_deletion_walks_the_derived_copy_graph(self):
        self.serving(version=2)
        self.store.put_pending(cv.Pending("D-03", cv.DELETION, 0, "2026-09-16T10:00:00+00:00"))
        outcome = self.apply("D-03", None)
        self.assertEqual(outcome["bucket"], "deleted")
        self.assertEqual((outcome["phase"], outcome["outstanding"]), (dl.PHYSICAL, []))
        self.assertEqual(self.storage.objects, {})
        self.assertEqual(self.agent.documents, {})
        self.assertEqual(self.store.pending, {})
        self.assertEqual(self.store.reflected("D-03").status, rs.DELETED)
        self.assertEqual(self.store.deletions()[0]["document_id"], "D-03")

    def test_deletion_proves_absence_even_when_every_generation_is_already_retired(self):
        """AB-13: retirement records an intention. Only reading the stores back proves the copies are gone.

        This is the case the baseline found: the retirement sweep had already marked every generation RETIRED, the
        old code skipped them, and deletion reported two of five copies proven while the content was in fact absent —
        removal without proof of removal.
        """
        self.store.put_generation(gn.Generation("D-03", 2, gn.RETIRED, ("S3", "S4")))
        self.store.put_reflected("D-03", 2, rs.IN_FORCE, gn.generation_id("D-03", 2))
        for section_id in ("S3", "S4"):
            self.storage.put("shared", gn.object_key("D-03", section_id, 2), "body")
            self.agent.documents[(KB["shared"][0], gn.custom_document_id("D-03", section_id, 2))] = "INDEXED"
        outcome = self.apply("D-03", None)
        self.assertEqual(outcome["bucket"], "deleted")
        self.assertEqual(outcome["generations_walked"], [2])
        self.assertEqual((outcome["phase"], outcome["outstanding"]), (dl.PHYSICAL, []))
        self.assertEqual((self.storage.objects, self.agent.documents), ({}, {}))

    def test_deletion_refuses_to_claim_completeness_while_a_copy_survives(self):
        """AB-3 stays strict: a copy the stores still return keeps the obligation open, whatever the records say."""
        self.serving(version=2)
        self.agent.delete_knowledge_base_documents = lambda **_kwargs: None   # removal silently does nothing
        outcome = self.apply("D-03", None)
        self.assertEqual(outcome["phase"], dl.LOGICAL)
        self.assertIn(dl.KNOWLEDGE_BASE_DOCUMENT, outcome["outstanding"])

    def test_a_deletion_ledger_entry_carries_no_content(self):
        self.serving(version=2)
        self.apply("D-03", None)
        text = json.dumps(self.store.deletions()[0])
        for forbidden in ("body", "question", "answer", "text"):
            self.assertNotIn(f'"{forbidden}"', text)

    def test_retirement_sweeps_every_generation_except_the_serving_one(self):
        """ADR-005 / FRS-003: a generation leaked by a concurrent apply is removed, not left retrievable for ever."""
        self.serving(version=2)                                             # the generation that was really serving
        self.store.put_generation(gn.Generation("D-03", 3, gn.SERVING, ("S3", "S4")))   # leaked by a concurrent apply
        for section_id in ("S3", "S4"):
            self.storage.put("shared", gn.object_key("D-03", section_id, 3), "body")
            self.agent.documents[(KB["shared"][0], gn.custom_document_id("D-03", section_id, 3))] = "INDEXED"
        retired = applier._retire_others("D-03", 4, self.storage, self.store, self.agent, KB)  # noqa: SLF001
        states = {int(g["version"]): g["state"] for g in self.store.generations("D-03")}
        self.assertEqual(retired, ["D-03#g2", "D-03#g3"])
        self.assertEqual(states, {2: gn.RETIRED, 3: gn.RETIRED})
        self.assertEqual((self.storage.objects, self.agent.documents), ({}, {}))

    def test_retirement_never_removes_the_generation_just_switched_to(self):
        """A rebuild at an unchanged version switches to the same generation; sweeping it would empty the index."""
        self.serving(version=2)
        before = (dict(self.storage.objects), dict(self.agent.documents))
        self.assertTrue(before[0] and before[1])                            # the fixture really did put copies there
        retired = applier._retire_others("D-03", 2, self.storage, self.store, self.agent, KB)  # noqa: SLF001
        self.assertEqual(retired, [])
        self.assertEqual((self.storage.objects, self.agent.documents), before)

    def test_a_late_change_after_removal_never_reinstates_the_document(self):
        """The document is removed because authority superseded it at v5; a replayed v4 must not bring it back."""
        self.serving(version=5)
        removed = self.apply("D-03", support.lifecycle("D-03", version=5, status=rs.SUPERSEDED,
                                                       superseded_by="D-06"))
        self.assertEqual(removed["bucket"], "deleted")
        self.assertEqual(self.store.reflected("D-03").status, rs.DELETED)
        outcome = self.apply("D-03", support.lifecycle("D-03", version=4))
        self.assertEqual((outcome["bucket"], outcome["decision"]), ("skipped", ca.AFTER_DELETE))

    def test_a_document_that_cannot_be_applied_is_reported_never_silently_dropped(self):
        records = support.FakeRecords({"D-06": support.lifecycle("D-06", version=1)})   # no source document for D-06
        self.store.put_pending(cv.Pending("D-06", cv.NEW_VERSION, 1, "2026-09-16T10:00:00+00:00"))
        report = applier.run({"document_ids": ["D-06"]}, records, self.source, self.storage, self.store, self.agent,
                             KB, "tla-s01e03-normal", sleep=lambda _s: None)
        self.assertEqual([f["document_id"] for f in report["failed"]], ["D-06"])
        self.assertEqual(report["applied"], [])
        self.assertIn("D-06", self.store.pending)          # a document that failed to converge stays pending

    def test_an_unreadable_authoritative_store_stops_the_run_rather_than_applying_a_guess(self):
        records = support.FakeRecords({"D-03": support.lifecycle("D-03")}, error=RuntimeError("Throttled"))
        with self.assertRaises(RuntimeError):
            applier.run({"document_ids": ["D-03"]}, records, self.source, self.storage, self.store, self.agent, KB,
                        "tla-s01e03-normal", sleep=lambda _s: None)


class Reconciliation(unittest.TestCase):
    """ADR-003 and ADR-007: the only mechanism that may establish completeness, and what it may claim when it does."""

    def setUp(self):
        self.store = support.FakeConvergence()

    def run_pass(self, records, repairs=None):
        asked = repairs if repairs is not None else []
        return reconciler.run({"run_id": "rec-test"}, records, self.store, applier="applier-function",
                              invoke=lambda name, ids: asked.append(sorted(ids)),
                              deployment="tla-s01e03-normal", now="2026-09-16T10:00:00+00:00"), asked

    def test_a_change_that_was_never_delivered_is_found_by_comparison(self):
        """FX-3 in one assertion: nothing in the pipeline saw this change, and reconciliation still finds it."""
        records = support.FakeRecords({"D-06": support.lifecycle("D-06", version=4)})
        self.store.put_reflected("D-06", 3, rs.IN_FORCE, "D-06#g3")
        summary, asked = self.run_pass(records)
        self.assertEqual([d["document_id"] for d in summary["divergent"]], ["D-06"])
        self.assertEqual(asked, [["D-06"]])
        self.assertEqual(self.store.pending["D-06"].detail, "RECONCILIATION_DRIFT")

    def test_a_document_authority_no_longer_has_is_extra_in_derived_state(self):
        self.store.put_reflected("D-12", 2, rs.IN_FORCE, "D-12#g2")
        summary, _ = self.run_pass(support.FakeRecords({}))
        self.assertEqual([d["document_id"] for d in summary["extra"]], ["D-12"])

    def test_a_document_never_indexed_is_missing_from_derived_state(self):
        summary, _ = self.run_pass(support.FakeRecords({"D-01": support.lifecycle("D-01", version=1)}))
        self.assertEqual([d["document_id"] for d in summary["missing"]], ["D-01"])

    def test_a_superseded_document_still_reflected_as_current_is_divergent(self):
        records = support.FakeRecords({"D-01": support.lifecycle("D-01", status=rs.SUPERSEDED, superseded_by="D-06")})
        self.store.put_reflected("D-01", 1, rs.IN_FORCE, "D-01#g1")
        summary, _ = self.run_pass(records)
        self.assertEqual([d["document_id"] for d in summary["divergent"]], ["D-01"])

    def test_a_completed_pass_advances_every_class_to_the_moment_it_started(self):
        """Never to "now": a change made during the pass may not have been seen by it."""
        summary, _ = self.run_pass(support.FakeRecords({}))
        self.assertEqual(sorted(summary["advanced"]), sorted(cv.CHANGE_CLASSES))
        self.assertEqual({moment for _c, moment in self.store.advances}, {"2026-09-16T10:00:00+00:00"})
        self.assertIsNotNone(summary["completed_at"])

    def test_a_failed_pass_proves_nothing_and_advances_nothing(self):
        records = support.FakeRecords({}, error=RuntimeError("ProvisionedThroughputExceeded"))
        summary, _ = self.run_pass(records)
        self.assertEqual(summary["failed"], "RuntimeError")
        self.assertEqual((summary["advanced"], self.store.advances, summary["completed_at"]), ([], [], None))

    def test_an_agreeing_comparison_requests_no_repairs(self):
        records = support.FakeRecords({"D-06": support.lifecycle("D-06", version=3)})
        self.store.put_reflected("D-06", 3, rs.IN_FORCE, "D-06#g3")
        summary, asked = self.run_pass(records)
        self.assertEqual((summary["missing"], summary["extra"], summary["divergent"], asked), ([], [], [], []))
        self.assertEqual(summary["documents_compared"], 1)


class FailureEvidence(unittest.TestCase):
    """A failure record must name the SITE, not merely the exception class.

    FX-2's replay failed with a bare `RuntimeError`. Two different raises in the build path share that class, the
    record kept neither message nor stage, and the variant's logs were destroyed with its stack during a correct
    cleanup. The failure became undiagnosable after the fact — so these tests pin what every failure must carry.
    """

    SOURCE = "# t\n\n## §3 Lessons\n\nCANARY-BODY-TEXT-NEVER-IN-EVIDENCE\n\n## §4 Pricing\n\nmore body\n"

    def setUp(self):
        self.store = support.FakeConvergence()
        self.storage = support.FakeStorage()
        self.source = support.FakeSource({"D-03": self.SOURCE})

    def apply(self, agent, records=None, sleep=lambda *_a, **_k: None):
        records = records or support.FakeRecords({"D-03": support.lifecycle("D-03", version=1)})
        return applier.run({"document_ids": ["D-03"]}, records, self.source, self.storage, self.store, agent, KB,
                           "test", sleep=sleep)

    def test_a_generation_that_never_indexes_records_the_stage_and_what_the_store_said(self):
        report = self.apply(support.FakeAgent(status="FAILED"))
        failure = report["failed"][0]
        self.assertEqual(failure["error"], "ChangeApplicationError")
        self.assertEqual((failure["stage"], failure["reason"]), ("index", "NOT_FULLY_INDEXED"))
        self.assertEqual(failure["generation_id"], "D-03#g1")
        self.assertEqual(failure["attempted_version"], 1)
        self.assertIn("FAILED", failure["detail"])
        self.assertTrue(failure["at"])

    def test_the_version_being_applied_and_the_one_still_serving_are_both_recorded(self):
        """Without both, a record cannot say whether derived state moved — the FX-2 question exactly."""
        self.store.put_reflected("D-03", 1, rs.IN_FORCE, "D-03#g1")
        records = support.FakeRecords({"D-03": support.lifecycle("D-03", version=2)})
        failure = self.apply(support.FakeAgent(status="FAILED"), records)["failed"][0]
        self.assertEqual((failure["attempted_version"], failure["serving_version"]), (2, 1))
        self.assertEqual(failure["serving_generation_id"], "D-03#g1")

    def test_an_sdk_error_keeps_its_code_and_operation_and_gains_the_same_context(self):
        class Denied(Exception):
            response = {"Error": {"Code": "AccessDeniedException"}}
            operation_name = "IngestKnowledgeBaseDocuments"

        class Refusing(support.FakeAgent):
            def ingest_knowledge_base_documents(self, **_kwargs):
                raise Denied("not authorized to perform: bedrock:IngestKnowledgeBaseDocuments")

        failure = self.apply(Refusing())["failed"][0]
        self.assertEqual((failure["error"], failure["code"]), ("Denied", "AccessDeniedException"))
        self.assertEqual(failure["operation"], "IngestKnowledgeBaseDocuments")
        self.assertEqual((failure["document_id"], failure["attempted_version"]), ("D-03", 1))
        self.assertIn("bedrock:IngestKnowledgeBaseDocuments", failure["message"])

    def test_a_failure_record_never_carries_document_text(self):
        failure = self.apply(support.FakeAgent(status="FAILED"))["failed"][0]
        self.assertNotIn("CANARY-BODY-TEXT-NEVER-IN-EVIDENCE", json.dumps(failure))

    def test_a_message_is_bounded_so_a_diagnosis_is_never_a_content_channel(self):
        class Chatty(support.FakeAgent):
            def ingest_knowledge_base_documents(self, **_kwargs):
                raise RuntimeError("x" * 5000)

        failure = self.apply(Chatty())["failed"][0]
        self.assertLessEqual(len(failure["message"]), applier.MESSAGE_LIMIT)

    def test_the_verify_raise_cannot_fire_through_the_normal_build_path(self):
        """Proof by construction, not by inference.

        `written` is keyed from the very objects `verify` is asked to expect, and each carries the version being
        applied — so INCOMPLETE and ATTRIBUTE_MISMATCH are unreachable. EMPTY returns down the quarantine branch
        before the raise. Therefore the only reachable failure in a build is the indexing one above.
        """
        from core import sections
        record = support.lifecycle("D-03", version=7)
        processed = sections.process(record, self.SOURCE)
        self.assertTrue(processed.objects)
        written = {o.section_id: dict(o.attributes(), record_version="7") for o in processed.objects}
        generation = gn.verify("D-03", 7, [o.section_id for o in processed.objects], written)
        self.assertEqual((generation.state, generation.problem), (gn.VERIFIED, None))

    def test_a_failed_rebuild_is_as_diagnosable_as_a_failed_change(self):
        from change import rebuild
        records = support.FakeRecords({"D-03": support.lifecycle("D-03", version=1)})
        report = rebuild.run({"document_ids": ["D-03"]}, records, self.source, self.storage, self.store,
                             support.FakeAgent(status="FAILED"), KB, "test", sleep=lambda *_a, **_k: None)
        failure = report["failed"][0]
        self.assertEqual((failure["stage"], failure["reason"]), ("index", "NOT_FULLY_INDEXED"))
        self.assertEqual(failure["generation_id"], "D-03#g1")
        self.assertTrue(failure["serving_generation_kept"])

    def test_a_reconciliation_that_could_not_read_says_what_failed(self):
        store = support.FakeConvergence()
        records = support.FakeRecords({}, error=RuntimeError("ProvisionedThroughputExceeded"))
        summary = reconciler.run({}, records, store, now="2026-09-16T10:00:00+00:00")
        self.assertEqual(summary["failed"], "RuntimeError")          # the existing contract is unchanged
        self.assertEqual(summary["failure"]["stage"], "export_and_compare")
        self.assertIn("ProvisionedThroughput", summary["failure"]["message"])


class MonotonicPromotion(unittest.TestCase):
    """AB-14: NO supported path may promote a generation that moves derived state backwards.

    Monotonicity is an invariant over transitions of derived state, not a feature of the incremental applier. Rebuild
    reached the switch without the applier's ordering decision and moved a document from v2 back to v1 — proved on
    the deployment, not argued. Each path that can promote is exercised here separately, because "the applier refuses
    it" is exactly the reasoning that left rebuild unguarded.
    """

    SOURCE = "# t\n\n## §3 Lessons\n\nlessons body\n\n## §4 Pricing\n\npricing body\n"
    NOTHING = lambda *_a, **_k: None  # noqa: E731 — no sleeping in unit tests

    def setUp(self):
        self.store = support.FakeConvergence()
        self.storage, self.agent = support.FakeStorage(), support.FakeAgent()
        self.source = support.FakeSource({"D-03": self.SOURCE})

    def records(self, version, **kwargs):
        return support.FakeRecords({"D-03": support.lifecycle("D-03", version=version, **kwargs)})

    def apply(self, version, **kwargs):
        return applier.run({"document_ids": ["D-03"]}, self.records(version, **kwargs), self.source, self.storage,
                           self.store, self.agent, KB, "test", sleep=MonotonicPromotion.NOTHING)

    def rebuild(self, version, event=None):
        from change import rebuild
        return rebuild.run(event or {"document_ids": ["D-03"]}, self.records(version), self.source, self.storage,
                           self.store, self.agent, KB, "test", sleep=MonotonicPromotion.NOTHING)

    def serving(self):
        reflected = self.store.reflected("D-03")
        return {"version": reflected.version, "generation_id": reflected.generation_id,
                "serving": sorted(g["generation_id"] for g in self.store.generations("D-03")
                                  if g["state"] == gn.SERVING)}

    def at_v2(self):
        """v1 serving, then a legitimate v2 — the starting point for every regression attempt below."""
        self.apply(1)
        self.apply(2)
        self.assertEqual(self.serving(), {"version": 2, "generation_id": "D-03#g2", "serving": ["D-03#g2"]})

    # E ── the forward case must keep working, or the guard has broken the system it protects
    def test_E_a_legitimate_newer_version_still_becomes_serving(self):
        self.at_v2()
        self.assertEqual([g["state"] for g in self.store.generations("D-03") if g["version"] == 1], [gn.RETIRED])

    # A ── incremental apply
    def test_A_an_incremental_replay_of_an_older_version_cannot_regress(self):
        self.at_v2()
        report = self.apply(1)
        self.assertEqual([s["decision"] for s in report["skipped"]], ["OLDER"])
        self.assertEqual(self.serving()["version"], 2)

    # B ── reconciliation repair
    def test_B_a_reconciliation_repair_cannot_regress(self):
        """Reconciliation repairs by asking the applier to converge the document — the repair must refuse too."""
        self.at_v2()
        asked = []
        summary = reconciler.run({}, self.records(1), self.store, applier="fn",
                                 invoke=lambda _fn, ids: asked.append(sorted(ids)))
        self.assertEqual(asked, [["D-03"]])                      # drift was found and a repair requested
        self.assertTrue(summary["divergent"] or summary["missing"] or summary["extra"])
        report = self.apply(1)                                   # the repair, applied through the same path
        self.assertEqual([s["decision"] for s in report["skipped"]], ["OLDER"])
        self.assertEqual(self.serving()["version"], 2)

    # C ── operator repair (ADR-008 clause 2: the same path, not a special one)
    def test_C_an_operator_repair_cannot_regress_and_says_why(self):
        self.at_v2()
        report = self.rebuild(1)
        self.assertEqual(report["rebuilt"], [])
        failure = report["failed"][0]
        self.assertEqual((failure["stage"], failure["reason"]), ("promote", "WOULD_REGRESS_SERVING_STATE"))
        self.assertEqual((failure["attempted_version"], failure["serving_version"]), (1, 2))
        self.assertTrue(failure["serving_generation_kept"])

    # D ── rebuild leaves nothing behind when it refuses
    def test_D_a_refused_rebuild_leaves_serving_state_and_the_stores_untouched(self):
        self.at_v2()
        before = (self.serving(), sorted(self.storage.objects), sorted(self.agent.documents))
        self.rebuild(1)
        self.assertEqual((self.serving(), sorted(self.storage.objects), sorted(self.agent.documents)), before)
        self.assertNotIn("D-03#g1", self.serving()["serving"])

    # F ── idempotence
    def test_F_rebuilding_the_version_already_serving_is_safe(self):
        self.at_v2()
        before = (sorted(self.storage.objects), sorted(self.agent.documents))
        report = self.rebuild(2)
        self.assertEqual([r["version"] for r in report["rebuilt"]], [2])
        self.assertEqual(self.serving(), {"version": 2, "generation_id": "D-03#g2", "serving": ["D-03#g2"]})
        self.assertEqual((sorted(self.storage.objects), sorted(self.agent.documents)), before)

    # G ── the canonical rebuild from current authority
    def test_G_a_canonical_rebuild_from_current_authority_still_works(self):
        self.at_v2()
        report = self.rebuild(2, event={"all": True})
        self.assertEqual([r["document_id"] for r in report["rebuilt"]], ["D-03"])
        self.assertEqual(report["failed"], [])
        self.assertEqual(self.serving()["version"], 2)

    # H ── retirement and switch behaviour
    def test_H_promotion_still_retires_every_other_generation_and_removes_its_copies(self):
        self.apply(1)
        self.apply(2)
        self.apply(3)
        self.assertEqual(self.serving()["serving"], ["D-03#g3"])
        self.assertEqual(sorted({g["state"] for g in self.store.generations("D-03") if g["version"] != 3}),
                         [gn.RETIRED])
        self.assertEqual([k for _t, k in self.storage.objects if "/g1/" in k or "/g2/" in k], [])
        self.assertEqual([i for _kb, i in self.agent.documents if i.endswith(("-g1", "-g2"))], [])

    # I ── the guard changes what may serve, never where content is routed
    def test_I_tier_routing_is_unchanged_by_the_promotion_guard(self):
        """CONFIDENTIAL routes to the SHARED tier — the tier is not the authorization boundary (CTL-010, CTL-012).

        Eligibility is decided by the mandatory constraint at request time, never by which knowledge base a section
        was written to. So the restricted tier holding nothing here is correct, not a leak, and the promotion guard
        must leave that routing exactly as it found it.
        """
        self.at_v2()
        shared_kb, restricted_kb = KB["shared"][0], KB["restricted"][0]
        self.assertEqual(sorted(i for kb, i in self.agent.documents if kb == shared_kb),
                         ["D-03-S3-g2", "D-03-S4-g2"])
        self.assertEqual([i for kb, i in self.agent.documents if kb == restricted_kb], [])


class RetirementNeverDestroysANewerGeneration(unittest.TestCase):
    """AB-16: an operation promoting version N may retire only generations OLDER than N.

    Observed on the deployment, not imagined — the audit recorded the overtaking directly (FX-3):

        16:23:44  applied D-06 v12  retired ["D-06#g11", "D-06#g13"]   ← swept a NEWER generation
        16:23:48  applied D-06 v13  retired ["D-06#g12"]

    A build writes `put_generation(g, VERIFIED)` and its derived copies BEFORE it promotes, so a concurrent apply
    can see a newer generation that already has a section object and an indexed document but has not yet switched.
    The slower operation's sweep then destroys artefacts belonging to the newer one. It left the canonical
    deployment serving D-06#g13 whose section object had been deleted — and reconciliation compares authoritative
    version against reflected version, so it cannot see a missing object: the drift is invisible to the mechanism
    that exists to find drift.

    AB-11 covered the converse (a leaked OLDER generation must not stay retrievable) and AB-14 covers which
    generation may BECOME serving. Neither covers which artefacts a completing operation may DESTROY.

    D-06 appears here only because that is where it happened; the defect is document-agnostic.
    """

    SOURCE = "# t\n\n## §1 Only section\n\nbody\n"
    NOTHING = lambda *_a, **_k: None  # noqa: E731 — no sleeping in unit tests

    def setUp(self):
        self.store = support.FakeConvergence()
        self.storage, self.agent = support.FakeStorage(), support.FakeAgent()
        self.source = support.FakeSource({"D-06": self.SOURCE})

    def record(self, version):
        return support.lifecycle("D-06", version=version, sections=[
            {"section_id": "S1", "title": "Only section", "label": None, "scope": None, "special_category": False}])

    def seed(self, version, state):
        """A generation WITH its derived copies present — the real in-flight state a build reaches before promoting."""
        self.store.put_generation(gn.Generation("D-06", version, state, ("S1",)))
        self.storage.put("shared", gn.object_key("D-06", "S1", version), "body")
        self.agent.documents[(KB["shared"][0], gn.custom_document_id("D-06", "S1", version))] = "INDEXED"

    def copies(self, version):
        """What actually survives for a generation: the consequences, not the returned list."""
        return {"section_object": ("shared", gn.object_key("D-06", "S1", version)) in self.storage.objects,
                "knowledge_base_document":
                    (KB["shared"][0], gn.custom_document_id("D-06", "S1", version)) in self.agent.documents,
                "state": {int(g["version"]): g["state"] for g in self.store.generations("D-06")}.get(version)}

    # A ── the older operation meets a newer VERIFIED generation: the newer one must survive intact
    def test_A_an_older_operation_must_not_destroy_a_newer_verified_generation(self):
        self.seed(11, gn.SERVING)
        self.seed(13, gn.VERIFIED)
        applier._retire_others("D-06", 12, self.storage, self.store, self.agent, KB)  # noqa: SLF001
        after = self.copies(13)
        self.assertTrue(after["section_object"], "g13's section object was destroyed by an older operation")
        self.assertTrue(after["knowledge_base_document"], "g13's knowledge-base document was destroyed")
        self.assertNotEqual(after["state"], gn.RETIRED, "g13 was marked RETIRED by an older operation")

    # B ── the same sweep must still remove genuinely older generations (AB-11 must not weaken)
    def test_B_genuinely_older_generations_are_still_retired(self):
        self.seed(11, gn.SERVING)
        self.seed(9, gn.VERIFIED)                      # leaked by an earlier concurrent apply — AB-11's case
        retired = applier._retire_others("D-06", 12, self.storage, self.store, self.agent, KB)  # noqa: SLF001
        self.assertEqual(retired, ["D-06#g11", "D-06#g9"])
        for version in (9, 11):
            after = self.copies(version)
            self.assertFalse(after["section_object"], f"g{version} should have been swept")
            self.assertFalse(after["knowledge_base_document"], f"g{version} should have been swept")
            self.assertEqual(after["state"], gn.RETIRED)

    # C ── a newer generation that already won the race is likewise untouchable
    def test_C_a_newer_generation_that_has_already_promoted_is_never_swept(self):
        self.seed(13, gn.SERVING)
        applier._retire_others("D-06", 12, self.storage, self.store, self.agent, KB)  # noqa: SLF001
        after = self.copies(13)
        self.assertTrue(after["section_object"] and after["knowledge_base_document"])
        self.assertNotEqual(after["state"], gn.RETIRED)

    # D ── the whole causal sequence, through the real change-application path
    def test_D_the_full_change_path_reproduces_the_observed_overtaking(self):
        self.store.put_reflected("D-06", 11, rs.IN_FORCE, "D-06#g11")
        self.seed(11, gn.SERVING)
        self.seed(13, gn.VERIFIED)                     # the newer build, artefacts written, promotion incomplete
        records = support.FakeRecords({"D-06": self.record(12)})
        outcome = applier.apply_one("D-06", self.record(12), records, self.source, self.storage, self.store,
                                    self.agent, KB,
                                    sleep=RetirementNeverDestroysANewerGeneration.NOTHING)
        # v12 over a serving v11 is a forward promotion, so AB-14 correctly allows it. The defect is what the
        # completing operation then destroys.
        self.assertEqual(outcome["bucket"], "applied")
        after = self.copies(13)
        self.assertTrue(after["section_object"], "the newer generation's object was destroyed by the v12 sweep")
        self.assertTrue(after["knowledge_base_document"], "the newer generation's indexed document was destroyed")
        self.assertNotEqual(after["state"], gn.RETIRED, "the newer generation was retired by the v12 sweep")


if __name__ == "__main__":
    unittest.main()
