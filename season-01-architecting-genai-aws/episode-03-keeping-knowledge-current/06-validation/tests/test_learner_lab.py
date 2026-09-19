"""The learner lab command surface — no AWS.

Three things are pinned here:

  1. every learner-visible result is a function of observed state, never a constant the command wrote in;
  2. each command refuses to run against the wrong part of the lab, with a reason a learner can act on;
  3. ending a lab part is idempotent.

A small mutation harness at the end re-executes the lab module with deliberate defects and requires each one to be
caught, so these tests are shown to be capable of failing.
"""
import argparse
import ast
import inspect
import io
import os
import sys
import types
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from harness import lab  # noqa: E402
from harness.common import tla_ops  # noqa: E402

LAB_SOURCE = inspect.getsource(lab)
NOW = datetime(2026, 9, 19, 12, 0, 0, tzinfo=timezone.utc)


def audit(outcome, retrieval=(), mismatches=(), states=None, control=None, invoked=False):
    return {"outcome": outcome, "failing_control": control, "retrieval": list(retrieval),
            "verification": {"status": "MISMATCH" if mismatches else "PASS", "mismatches": list(mismatches)},
            "convergence": {"document_states": states or {}}, "generation": {"invoked": invoked}}


STALE = [{"chunk_id": "c1", "document_id": "D-02", "section_id": "S1", "label": "INTERNAL", "scope": None,
          "record_version": 1}, {"chunk_id": "c2", "document_id": "D-02", "section_id": "S2", "label": "INTERNAL",
                                 "scope": None, "record_version": 1}]


# ── 1 · results come from observed state ────────────────────────────────────────────────────────────────────────────
class AskView(unittest.TestCase):
    def test_the_refusal_is_read_from_the_audit_record(self):
        lines = "\n".join(lab.ask_view("q", "P-01", audit(
            "WITHHELD_NOT_CURRENT", STALE, [{"chunk_id": "c1", "reason": "NOT_CURRENT"},
                                            {"chunk_id": "c2", "reason": "NOT_CURRENT"}],
            {"D-02": "KNOWN_SUPERSEDED_WITHDRAWN_DELETED"}, "CTL-030"), {"citations": []}))
        self.assertIn("WITHHELD_NOT_CURRENT", lines)
        self.assertIn("stopped at CTL-030", lines)
        self.assertIn("D-02-S1 v1  (INTERNAL / no scope)", lines, "the retrieved stale copy must be shown")
        self.assertIn("D-02  KNOWN_SUPERSEDED_WITHDRAWN_DELETED", lines)
        self.assertIn("D-02-S2 v1  NOT_CURRENT", lines, "a refusal is named per copy")
        self.assertIn("model invoked  no", lines)
        self.assertIn("cited          nothing", lines)
        self.assertIn("=> COPY: PRESENT (retrieved D-02-S1, D-02-S2)   REQUEST: WITHHELD_NOT_CURRENT", lines,
                      "the key recording frame is one line, built from the audit record")

    def test_the_same_request_answered_is_shown_as_answered(self):
        lines = "\n".join(lab.ask_view("q", "P-01", audit("ANSWERED", STALE, (), {"D-02": "KNOWN_CURRENT"},
                                                          invoked=True),
                                       {"answer": "Wear boots.", "citations": [
                                           {"document_id": "D-02", "section_id": "S1", "record_version": 1}]}))
        self.assertIn("outcome        ANSWERED", lines)
        self.assertNotIn("WITHHELD", lines)
        self.assertNotIn("stopped at", lines)
        self.assertNotIn("COPY: PRESENT", lines, "no refusal banner when nothing was refused")
        self.assertIn("model invoked  yes", lines)
        self.assertIn("D-02-S1 v1", lines)
        self.assertIn("Wear boots.", lines)

    def test_an_unexpected_outcome_is_passed_through_not_corrected(self):
        lines = "\n".join(lab.ask_view("q", "P-01", audit("SOMETHING_NEW"), {}))
        self.assertIn("SOMETHING_NEW", lines)

    def test_a_missing_audit_record_is_reported_never_filled_in(self):
        lines = "\n".join(lab.ask_view("q", "P-01", None, {"answer": "text"}))
        self.assertIn("UNKNOWN", lines)
        self.assertNotIn("ANSWERED", lines)

    def test_an_empty_retrieval_says_nothing_was_retrieved(self):
        self.assertIn("  nothing", lab.ask_view("q", "P-01", audit("NO_RELEVANT_CONTENT"), {}))

    def test_no_outcome_or_state_is_hard_coded_in_the_module(self):
        """The module may NAME no request outcome or document state as a literal it could print."""
        for literal in ("WITHHELD_NOT_CURRENT", "ANSWERED", "NO_RELEVANT_CONTENT", "KNOWN_CURRENT",
                        "KNOWN_SUPERSEDED_WITHDRAWN_DELETED", "NOT_CURRENT", "CTL-030"):
            self.assertNotIn(f'"{literal}"', LAB_SOURCE, literal)
            self.assertNotIn(f"'{literal}'", LAB_SOURCE, literal)


class InspectView(unittest.TestCase):
    RECORD = {"document_id": "D-02", "status": "WITHDRAWN", "version": 1, "document_label": "INTERNAL",
              "document_scope": None}
    CHUNKS = {"chunks": [{"document_id": "D-02", "section_id": "S1", "record_version": 1, "label": "INTERNAL",
                          "scope": None}], "section_objects": ["sections/D-02/g1/S1.txt"]}

    def view(self, record, reflected, copies, pending=None):
        return "\n".join(lab.inspect_view("D-02", record, reflected, copies, pending, "OFF since creation"))

    def test_diverged_when_authority_withdrew_and_the_copy_remains(self):
        text = self.view(self.RECORD, {"status": "IN_FORCE", "version": 1}, self.CHUNKS)
        self.assertRegex(text, r"copies\s+PRESENT")
        self.assertIn("=> DIVERGED: authority says WITHDRAWN; the index still believes IN_FORCE.", text)
        self.assertIn("=> The copy exists. It must not be trusted.", text)

    def test_converged_when_authority_withdrew_and_nothing_remains(self):
        text = self.view(self.RECORD, {"status": "DELETED", "version": 1}, {"chunks": [], "section_objects": []})
        self.assertIn("ABSENT", text)
        self.assertIn("Converged: authority says WITHDRAWN", text)

    def test_agreement_when_versions_and_status_match(self):
        record = dict(self.RECORD, status="IN_FORCE")
        text = self.view(record, {"status": "IN_FORCE", "version": 1}, self.CHUNKS)
        self.assertIn("In agreement", text)

    def test_a_version_disagreement_is_not_called_agreement(self):
        record = dict(self.RECORD, status="IN_FORCE", version=2)
        self.assertNotIn("In agreement", self.view(record, {"status": "IN_FORCE", "version": 1}, self.CHUNKS))

    def test_pending_is_reported_from_the_pending_entry(self):
        record = dict(self.RECORD, status="IN_FORCE")
        text = self.view(record, {"status": "IN_FORCE", "version": 1}, self.CHUNKS,
                         {"change_class": "reclassify_up", "attempts": 1})
        self.assertIn("YES — reclassify_up, attempts 1", text)

    def test_a_deleted_record_is_shown_as_not_held(self):
        self.assertIn("NOT HELD", self.view(None, None, {"chunks": [], "section_objects": []}))


class Repairs(unittest.TestCase):
    def test_absent_after_the_pass_means_repaired(self):
        self.assertEqual(lab.repair_outcomes(["D-02"], {}, {}), {"D-02": "REPAIRED"})

    def test_attempts_rising_means_the_retry_ran_and_failed(self):
        self.assertEqual(lab.repair_outcomes(["D-04"], {"D-04": {"attempts": 1}}, {"D-04": {"attempts": 2}}),
                         {"D-04": "RETRY FAILED"})

    def test_unchanged_attempts_means_still_waiting(self):
        self.assertEqual(lab.repair_outcomes(["D-04"], {"D-04": {"attempts": 1}}, {"D-04": {"attempts": 1}}),
                         {"D-04": "WAITING"})

    def test_a_fresh_entry_with_no_attempt_is_waiting_not_failed(self):
        self.assertEqual(lab.repair_outcomes(["D-02"], {}, {"D-02": {"attempts": 0}}), {"D-02": "WAITING"})


class ReconcileView(unittest.TestCase):
    PASS = {"documents_compared": 15, "missing": [], "extra": [],
            "divergent": [{"document_id": "D-02", "authoritative_status": "WITHDRAWN", "reflected_status": "IN_FORCE"}],
            "repairs_requested": ["D-02"], "escalation": {"breaches": {}}}

    def test_divergence_repair_and_confirmation(self):
        text = "\n".join(lab.reconcile_view(self.PASS, {"D-02": "REPAIRED"}, {},
                                            {"documents_compared": 15, "missing": [], "extra": [], "divergent": [],
                                             "repairs_requested": []}))
        self.assertIn("compared 15 documents", text)
        self.assertIn("D-02 (authority WITHDRAWN, index IN_FORCE)", text)
        self.assertIn("D-02  REPAIRED", text)
        self.assertIn("CONVERGED", text)

    def test_an_unclean_confirmation_is_never_called_converged(self):
        text = "\n".join(lab.reconcile_view(self.PASS, {"D-02": "REPAIRED"}, {},
                                            {"documents_compared": 15, "repairs_requested": ["D-02"]}))
        self.assertNotIn("CONVERGED", text)

    def test_a_breach_names_class_window_and_document(self):
        summary = dict(self.PASS, divergent=[], escalation={"breaches": {"reclassify_up": ["D-04"]},
                                                            "newly_escalated": ["D-04"]})
        text = "\n".join(lab.reconcile_view(summary, {"D-04": "RETRY FAILED"}, {"D-04": {}}))
        self.assertIn("BREACHED  reclassify_up (window 0 s): D-04 — ESCALATED on this pass — alert raised", text)
        self.assertIn("still pending  D-04", text)

    def test_a_breach_already_escalated_is_not_described_as_a_new_alert(self):
        """Rehearsal find: the recovery pass still sees the breach it is about to repair; it raises nothing new."""
        summary = dict(self.PASS, divergent=[], escalation={"breaches": {"reclassify_up": ["D-04"]},
                                                            "newly_escalated": []})
        text = "\n".join(lab.reconcile_view(summary, {"D-04": "REPAIRED"}, {}))
        self.assertIn("already escalated; not raised again", text)
        self.assertNotIn("alert raised", text)

    def test_every_difference_shape_the_reconciler_reports_is_described_from_its_own_fields(self):
        """The reconciler reports statuses for a status divergence and versions for everything else (rehearsal find)."""
        summary = {"documents_compared": 15, "escalation": {},
                   "missing": [{"document_id": "D-07", "authoritative_version": 3, "reflected": None}],
                   "extra": [{"document_id": "D-99", "authoritative": None, "reflected_version": 2}],
                   "divergent": [{"document_id": "D-04", "authoritative_version": 2, "reflected_version": 1},
                                 {"document_id": "D-02", "authoritative_status": "WITHDRAWN",
                                  "reflected_status": "IN_FORCE"}]}
        text = "\n".join(lab.reconcile_view(summary, {}, {}))
        self.assertIn("D-07 (authority v3, index holds nothing)", text)
        self.assertIn("D-99 (authority holds nothing, index v2)", text)
        self.assertIn("D-04 (authority v2, index v1)", text)
        self.assertIn("D-02 (authority WITHDRAWN, index IN_FORCE)", text)
        self.assertNotIn("None", text)

    def test_a_repeated_error_code_is_printed_once(self):
        self.assertEqual(lab.describe_failure({"error": "AccessDenied", "code": "AccessDenied",
                                               "operation": "GetObject"}), "AccessDenied on GetObject")
        self.assertEqual(lab.describe_failure({"error": "ClientError", "code": "NoSuchKey", "operation": "GetObject"}),
                         "ClientError NoSuchKey on GetObject")

    def test_no_breach_is_said_plainly(self):
        self.assertIn("  no change has outlived its window", lab.reconcile_view(self.PASS, {}, {}))


class IncidentView(unittest.TestCase):
    ENTRY = {"change_class": "reclassify_up", "noticed_at": (NOW - timedelta(seconds=95)).isoformat(),
             "attempts": 2, "last_attempt_at": NOW.isoformat(), "escalated_at": NOW.isoformat()}

    def test_age_window_breach_attempts_and_escalation(self):
        text = "\n".join(lab.incident_view("D-04", self.ENTRY, NOW, {"error": "ClientError", "code": "NoSuchKey",
                                                                      "operation": "GetObject", "attempted_version": 2,
                                                                      "serving_version": 1},
                                           {"name": "a", "state": "ALARM", "since": "t"}))
        self.assertIn("PENDING", text)
        self.assertIn("age 1 min 35 s", text)
        self.assertIn("0 s — BREACHED", text)
        self.assertRegex(text, r"attempts\s+2   \(last")
        self.assertIn("NoSuchKey on GetObject", text)
        self.assertIn("ALARM", text)

    def test_not_yet_escalated_says_so(self):
        text = "\n".join(lab.incident_view("D-04", dict(self.ENTRY, escalated_at=None, attempts=1), NOW, None, None))
        self.assertIn("not yet", text)

    def test_no_pending_entry_is_no_open_incident(self):
        text = "\n".join(lab.incident_view("D-04", None, NOW, None, {"name": "a", "state": "ALARM", "since": "t"},
                                           {"version": 2, "document_label": "CONFIDENTIAL"},
                                           {"status": "IN_FORCE", "version": 2}))
        self.assertIn("No open incident for D-04", text)
        self.assertIn("returns to OK by itself", text, "an alarm still showing after repair is explained")


# ── 2 · each command runs against the right part only ───────────────────────────────────────────────────────────────
class PartGuards(unittest.TestCase):
    def test_no_lab_running_is_a_refusal_that_says_how_to_start(self):
        with self.assertRaises(lab.LabError) as refused:
            lab.choose_part([])
        self.assertIn("lab-up delivery-off", str(refused.exception))

    def test_part_a_steps_refuse_on_part_b(self):
        with self.assertRaises(lab.LabError) as refused:
            lab.choose_part(["delivery-on"], required="delivery-off")
        self.assertIn("WITHOUT change notifications", str(refused.exception))

    def test_part_b_steps_refuse_on_part_a(self):
        with self.assertRaises(lab.LabError) as refused:
            lab.choose_part(["delivery-off"], required="delivery-on")
        self.assertIn("LIVE change notifications", str(refused.exception))

    @unittest.skipUnless(__import__("importlib").util.find_spec("botocore"), "botocore is not installed")
    def test_an_aws_failure_is_one_readable_line_not_a_traceback(self):
        from botocore.exceptions import ClientError

        def expire():
            raise ClientError({"Error": {"Code": "InvalidSignatureException", "Message": "Signature expired"}}, "GetItem")
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(lab.run(expire), 3)
        self.assertIn("AWS REQUEST FAILED: InvalidSignatureException", out.getvalue())
        self.assertIn("safe to repeat", out.getvalue())

    def test_a_programming_error_is_not_disguised_as_an_aws_failure(self):
        def broken():
            raise KeyError("bug")
        with self.assertRaises(KeyError):
            lab.run(broken)

    def test_both_parts_running_is_refused(self):
        with self.assertRaises(lab.LabError):
            lab.choose_part(["delivery-off", "delivery-on"])

    def test_running_parts_reads_only_lab_stacks(self):
        self.assertEqual(lab.running_parts({"normal": "CREATE_COMPLETE", "no-delivery": "CREATE_COMPLETE"}), [])
        self.assertEqual(lab.running_parts({"lab-delivery-on": "CREATE_COMPLETE"}), ["delivery-on"])

    def test_learner_output_fits_a_100_column_recording_terminal(self):
        long_reason = "word " * 60
        out = io.StringIO()
        with redirect_stdout(out):
            lab.run(lambda: (_ for _ in ()).throw(lab.LabError(long_reason)))
        self.assertTrue(all(len(line) <= lab.WIDTH for line in out.getvalue().splitlines()))
        views = [lab.inspect_view("D-02", InspectView.RECORD, {"status": "IN_FORCE", "version": 1},
                                  InspectView.CHUNKS, None, "OFF since creation (stream mapping Disabled)"),
                 lab.incident_view("D-04", None, NOW, None, {"name": "tla-s01e03-lab-on-window-breach",
                                                             "state": "ALARM", "since": NOW.isoformat()},
                                   {"version": 2, "document_label": "CONFIDENTIAL"}, {"status": "IN_FORCE", "version": 2})]
        for view in views:
            for line in view:
                self.assertLessEqual(len(line), lab.WIDTH, line)

    def test_a_refusal_is_one_line_and_exit_code_2(self):
        def refuse():
            raise lab.LabError("because")
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(lab.run(refuse), 2)
        self.assertEqual(out.getvalue(), "REFUSED: because\n")

    def test_only_d04_has_an_upward_reclassification(self):
        self.assertEqual(sorted(lab.RECLASSIFY_UP_TO), ["D-04"])
        self.assertEqual(lab.RECLASSIFY_UP_TO["D-04"]["document_label"], "CONFIDENTIAL")


class LabDeployments(unittest.TestCase):
    def test_the_verbs_that_change_state_declare_their_part(self):
        for function, part in ((lab.cmd_withdraw, "delivery-off"), (lab.cmd_obstruct, "delivery-on"),
                               (lab.cmd_reclassify_up, "delivery-on"), (lab.cmd_unobstruct, "delivery-on"),
                               (lab.cmd_incident, "delivery-on")):
            self.assertIn(f'lab_target(required="{part}")', inspect.getsource(function), function.__name__)

    def test_part_a_is_created_without_delivery_and_part_b_with_it(self):
        self.assertEqual(tla_ops.change_notifications_enabled(tla_ops.LAB_PARTS["delivery-off"]), "false")
        self.assertEqual(tla_ops.change_notifications_enabled(tla_ops.LAB_PARTS["delivery-on"]), "true")

    def test_the_lab_never_uses_the_normal_or_an_evidence_stack(self):
        names = {tla_ops.names(v, "123456789012")["stack"] for v in tla_ops.LAB_VARIANTS}
        self.assertEqual(names, {"tla-s01e03-lab-off", "tla-s01e03-lab-on"})
        self.assertTrue(tla_ops.LAB_VARIANTS.isdisjoint({"normal", "no-delivery"}))

    def test_lab_deployments_run_the_normal_code(self):
        self.assertTrue(tla_ops.LAB_VARIANTS <= tla_ops.CONFIGURATION_VARIANTS)
        for variant in tla_ops.LAB_VARIANTS:
            self.assertIsNone(tla_ops.VARIANTS[variant][1])

    def test_lab_resources_are_tagged_lab(self):
        for variant in tla_ops.LAB_VARIANTS:
            self.assertIn({"Key": "Variant", "Value": "lab"}, tla_ops.tags(variant))

    def test_one_part_at_a_time(self):
        self.assertEqual(tla_ops.lab_conflicts({"normal": "x", "lab-delivery-off": "x"}, "lab-delivery-on"),
                         ["lab-delivery-off"])
        self.assertEqual(tla_ops.lab_conflicts({"normal": "x", "lab-delivery-on": "x"}, "lab-delivery-on"), [])
        self.assertEqual(tla_ops.lab_conflicts({"no-delivery": "x"}, "lab-delivery-off"), ["no-delivery"])

    def test_a_lab_variant_cannot_be_deployed_around_lab_up(self):
        with self.assertRaises(SystemExit) as refused:
            tla_ops.cmd_deploy(argparse.Namespace(variant="lab-delivery-off"))
        self.assertIn("lab-up", str(refused.exception))



class SourcePresence(unittest.TestCase):
    """The records bucket answers 403 to every reader but the change function, whether or not the object exists."""

    class S3:
        def __init__(self, keys):
            self.keys = keys

        def list_objects_v2(self, Bucket, Prefix):
            return {"Contents": [{"Key": k} for k in self.keys if k.startswith(Prefix)]}

        def head_object(self, **_):
            raise AssertionError("HeadObject answers 403 here and must never be used as a presence check")

        get_object = head_object

    def test_present_only_on_an_exact_key(self):
        self.assertTrue(lab.source_present(self.S3(["records/D-04.md"]), "b", "records/D-04.md"))
        self.assertFalse(lab.source_present(self.S3(["records/D-04.md.bak"]), "b", "records/D-04.md"))
        self.assertFalse(lab.source_present(self.S3([]), "b", "records/D-04.md"))



class SourceBoundary(unittest.TestCase):
    def test_obstruct_and_unobstruct_never_read_the_object(self):
        for function in (lab.cmd_obstruct, lab.cmd_unobstruct):
            source = inspect.getsource(function)
            self.assertNotIn("head_object", source)
            self.assertNotIn("get_object", source)
            self.assertIn("source_present(", source)


class CommandLine(unittest.TestCase):
    def test_the_lab_verbs_are_exactly_the_learner_commands(self):
        parser = argparse.ArgumentParser()
        sub = parser.add_subparsers(dest="command")
        lab.add_cli(sub)
        self.assertEqual(sorted(sub.choices), sorted(lab.learner_commands()))
        for name, (function, _) in lab.learner_commands().items():
            self.assertIs(inspect.getmodule(function), lab, name)
            self.assertTrue(name.startswith("lab-"), name)


# ── 3 · ending a lab part is idempotent ─────────────────────────────────────────────────────────────────────────────
class Idempotence(unittest.TestCase):
    def absent_session(self):
        class Missing(Exception):
            pass

        class Cfn:
            def describe_stacks(self, StackName):
                raise Missing(f"Stack with id {StackName} does not exist")

        class S3:
            def get_paginator(self, _):
                class Pages:
                    def paginate(self, **_):
                        raise Missing("An error occurred (NoSuchBucket)")
                return Pages()

            def delete_bucket(self, Bucket):
                raise Missing("An error occurred (NoSuchBucket)")

        class Session:
            def client(self, name, **_):
                return {"cloudformation": Cfn(), "s3": S3(), "iam": object()}[name]
        return Session()

    def test_cleaning_an_absent_part_twice_succeeds_both_times(self):
        for variant in sorted(tla_ops.LAB_VARIANTS):
            for _ in range(2):
                failed, lines = tla_ops.cleanup(self.absent_session(), "123456789012", [variant])
                self.assertFalse(failed, lines)
                self.assertTrue(any("not present" in line for line in lines), lines)


# ── mutation harness: the tests above must be able to fail ──────────────────────────────────────────────────────────
MUTANTS = {
    "absent treated as waiting": ('outcomes[document_id] = "REPAIRED"', 'outcomes[document_id] = "WAITING"'),
    "retry success invented": ('> int(was.get("attempts") or 0)', '>= int(was.get("attempts") or 0)'),
    "refusal banner without a refusal": ("    if mismatches:\n        refused", "    if True:\n        refused"),
    "outcome hard-coded": ("f\"  outcome        {audit.get('outcome')}\"", "f\"  outcome        {'ANSWERED'}\""),
    "missing audit filled in": ('if not audit:\n        return', 'if False:\n        return'),
    "presence called currency": ('if chunks and authority != "IN_FORCE":', 'if False:'),
    "breach hidden": ("if breaches:", "if False:"),
    "part guard dropped": ("if required and part != required:", "if False:"),
    "window check inverted": ("age > window", "age < window"),
    "version divergence shown as status": ('if "authoritative_status" in entry:', 'if True:'),
    "presence by prefix only": ('return any(item.get("Key") == key for item in listed)', 'return bool(listed)'),
    "every breach called a new alert": ("if document_id in newly", "if True"),
    "unclean confirmation called converged": ('or confirmation.get("repairs_requested"))', ')'),
}


def load_mutant(original, replacement):
    source = LAB_SOURCE
    assert source.count(original) >= 1, original
    module = types.ModuleType("harness.lab_mutant")
    module.__dict__["__name__"] = "harness.lab_mutant"
    exec(compile(source.replace(original, replacement, 1), "lab_mutant", "exec"), module.__dict__)  # noqa: S102
    return module


def surviving(module):
    """Run this file's view/guard tests against a mutant; return True if every one still passes."""
    loader, suite = unittest.TestLoader(), unittest.TestSuite()
    for case in (AskView, InspectView, Repairs, ReconcileView, IncidentView, PartGuards, SourcePresence):
        suite.addTests(loader.loadTestsFromTestCase(case))
    real = globals()["lab"]
    globals()["lab"] = module
    try:
        result = unittest.TestResult()
        suite.run(result)
    finally:
        globals()["lab"] = real
    return result.wasSuccessful()


class MutationHarness(unittest.TestCase):
    def test_the_unmutated_module_passes(self):
        self.assertTrue(surviving(load_mutant("WIDTH = 100", "WIDTH = 100")))

    def test_every_mutant_is_killed(self):
        survivors = [name for name, (a, b) in MUTANTS.items() if surviving(load_mutant(a, b))]
        self.assertEqual(survivors, [], "these defects would pass unnoticed")


if __name__ == "__main__":
    unittest.main()
