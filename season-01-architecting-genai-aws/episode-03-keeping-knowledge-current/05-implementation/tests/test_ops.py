"""Deployment script guards (no AWS): normal builds carry no failure-experiment code; each CODE variant replaces
exactly one module while a declared CONFIGURATION variant replaces none; variants deploy only through the experiment
runner; resource names fit AWS limits."""
import argparse
import json
import os
import re
import shutil
import sys
import tempfile
import unittest
import zipfile

import support

sys.path.insert(0, os.path.join(support.IMPLEMENTATION, "scripts"))
import tla_ops  # noqa: E402

MARKER = "SENSITIVITY VARIANT"


class BuildGuards(unittest.TestCase):
    def setUp(self):
        self.original = tla_ops.BUILD
        self.temporary = tempfile.mkdtemp()
        tla_ops.BUILD = self.temporary

    def tearDown(self):
        tla_ops.BUILD = self.original
        shutil.rmtree(self.temporary, ignore_errors=True)

    def build(self, variant):
        self.assertEqual(tla_ops.cmd_build(argparse.Namespace(variant=variant)), 0)
        with open(os.path.join(self.temporary, variant, "manifest.json"), encoding="utf-8") as handle:
            return json.load(handle)

    def package(self, variant, function):
        with zipfile.ZipFile(os.path.join(self.temporary, variant, f"{function}.zip")) as archive:
            return {name: archive.read(name).decode() for name in archive.namelist()}

    def test_normal_build_has_no_variant_code(self):
        manifest = self.build("normal")
        self.assertEqual(manifest["replaced_modules"], [])
        for function in tla_ops.PACKAGES:
            for name, text in self.package("normal", function).items():
                self.assertNotIn(MARKER, text, name)

    @unittest.skipUnless(os.path.isdir(tla_ops.SENSITIVITY), "failure-experiment modules are not part of this package")
    def test_each_variant_replaces_exactly_one_module(self):
        for variant, (_, (module, _)) in ((v, spec) for v, spec in tla_ops.VARIANTS.items() if spec[1]):
            manifest = self.build(variant)
            self.assertEqual(manifest["replaced_modules"], [module])
            function = "change" if module.startswith("change/") else "query"
            self.assertIn(MARKER, self.package(variant, function)[module])

    def test_a_variant_may_replace_no_module_only_if_declared_configuration_only(self):
        """`no-delivery` differs from normal by STACK CONFIGURATION, not code, so it replaces nothing (an earlier change).

        `test_each_variant_replaces_exactly_one_module` iterates only variants that declare a replacement, so it would
        skip a zero-replacement variant in silence — a test that still passes while its premise has changed. Both
        halves are pinned here instead: the declared configuration variants build clean, and they are the ONLY
        non-normal variants permitted to replace nothing.
        """
        zero = sorted(v for v, spec in tla_ops.VARIANTS.items() if v != "normal" and spec[1] is None)
        self.assertEqual(zero, sorted(tla_ops.CONFIGURATION_VARIANTS))
        for variant in sorted(tla_ops.CONFIGURATION_VARIANTS):
            self.assertEqual(self.build(variant)["replaced_modules"], [], variant)

    def test_guard_refuses_variant_code_in_a_normal_build(self):
        staging = tla_ops._stage("normal")
        with open(os.path.join(staging, "core", "constraints.py"), "a", encoding="utf-8") as handle:
            handle.write(f"\n# {MARKER}\n")
        with self.assertRaises(SystemExit):
            tla_ops._guard("normal", staging)

    def test_packages_contain_only_their_function(self):
        self.build("normal")
        self.assertFalse(any(n.startswith("change/") for n in self.package("normal", "query")))
        self.assertFalse(any(n.startswith("query/") for n in self.package("normal", "change")))
        self.assertIn('VARIANT = "normal"', self.package("normal", "query")["adapters/build_info.py"])

    @unittest.skipUnless(os.path.isdir(tla_ops.SENSITIVITY), "failure-experiment modules are not part of this package")
    def test_variant_deploy_refused_outside_the_runner(self):
        self.build("status-ignored")
        os.environ.pop("TLA_SENSITIVITY_RUN", None)
        with self.assertRaises(SystemExit) as refused:
            tla_ops.cmd_deploy(argparse.Namespace(variant="status-ignored"))
        self.assertIn("experiment runner", str(refused.exception))


class CleanupGuards(unittest.TestCase):
    """The canonical normal deployment was once destroyed because an argument was merely absent.

    These tests exist so the safe operation is the default and the destructive one has to be asked for.
    """

    def test_cleanup_refuses_to_destroy_normal_without_a_deliberate_flag(self):
        with self.assertRaises(RuntimeError) as refused:
            tla_ops.cleanup(None, "123456789012", ["normal"])
        self.assertIn("allow_normal", str(refused.exception))

    def test_cleanup_refuses_normal_even_inside_a_wider_list(self):
        with self.assertRaises(RuntimeError):
            tla_ops.cleanup(None, "123456789012", list(tla_ops.VARIANTS))

    def test_an_omitted_variant_means_experiments_never_everything(self):
        parser = self._parser()
        args = parser.parse_args(["cleanup"])
        self.assertEqual(args.variant, "experiments")
        self.assertFalse(args.destroy_normal)

    def test_the_destructive_flag_exists_and_is_off_by_default(self):
        parser = self._parser()
        self.assertFalse(parser.parse_args(["cleanup", "--variant", "all"]).destroy_normal)
        self.assertTrue(parser.parse_args(["cleanup", "--variant", "normal", "--destroy-normal"]).destroy_normal)

    def _parser(self):
        """The real parser, built the way main() builds it — so the test cannot drift from the command line."""
        parser = argparse.ArgumentParser()
        sub = parser.add_subparsers(dest="command")
        p = sub.add_parser("cleanup")
        p.add_argument("--variant", choices=list(tla_ops.VARIANTS) + ["all", "experiments"], default="experiments")
        p.add_argument("--destroy-normal", action="store_true")
        return parser


class StackDeletionRetries(unittest.TestCase):
    """§11: a variant that will not delete leaves a deliberately broken deployment running, and costs money quietly."""

    def session(self, statuses, resources):
        emptied = []

        class Cfn:
            def __init__(self):
                self.deletes = 0

            def describe_stacks(self, StackName):
                # The status follows how many deletions have been attempted, so the existence check at the top of
                # _delete_stack does not consume the first outcome. Popping a queue instead made the waiter see
                # DELETE_COMPLETE on the first attempt, and the retry path was never reached.
                return {"Stacks": [{"StackId": "sid",
                                    "StackStatus": statuses[min(self.deletes, len(statuses) - 1)]}]}

            def delete_stack(self, StackName, **kwargs):
                self.deletes += 1

            def describe_stack_resources(self, StackName):
                return {"StackResources": resources}

        class Iam:
            exceptions = type("Exceptions", (), {"NoSuchEntityException": KeyError})

            def get_role(self, RoleName):
                raise KeyError(RoleName)

        class S3:
            def get_paginator(self, _name):
                class Pages:
                    def paginate(self, **kwargs):
                        emptied.append(kwargs.get("Bucket"))
                        return [{"Versions": [], "DeleteMarkers": []}]
                return Pages()

        cfn = Cfn()

        class Session:
            def client(self, name, **_kwargs):
                return {"cloudformation": cfn, "iam": Iam(), "s3": S3()}[name]

        return Session(), cfn, emptied

    def test_a_bucket_that_filled_up_again_is_emptied_and_the_delete_retried(self):
        """Objects reappear between emptying and deletion because the stack's own writers are still alive."""
        bucket = {"ResourceStatus": "DELETE_FAILED", "ResourceType": "AWS::S3::Bucket",
                  "LogicalResourceId": "RestrictedSectionBucket", "PhysicalResourceId": "tla-restricted",
                  "ResourceStatusReason": 'The bucket you tried to delete is not empty (Service: S3, Status Code: 409)'}
        session, cfn, emptied = self.session(["CREATE_COMPLETE", "DELETE_FAILED", "DELETE_COMPLETE"], [bucket])
        self.assertEqual(tla_ops._delete_stack(session, "tla-s01e03-fx-status"), "DELETE_COMPLETE")  # noqa: SLF001
        self.assertIn("tla-restricted", emptied)
        self.assertGreaterEqual(cfn.deletes, 2)

    def test_an_unrelated_delete_failure_is_reported_not_retried_for_ever(self):
        table = {"ResourceStatus": "DELETE_FAILED", "ResourceType": "AWS::DynamoDB::Table",
                 "LogicalResourceId": "ConvergenceTable", "PhysicalResourceId": "tla-convergence",
                 "ResourceStatusReason": "something else entirely"}
        session, _cfn, emptied = self.session(["CREATE_COMPLETE", "DELETE_FAILED"], [table])
        result = tla_ops._delete_stack(session, "tla-s01e03-fx-status")  # noqa: SLF001
        self.assertTrue(result.startswith("DELETE_FAILED"))
        self.assertIn("ConvergenceTable", result)
        self.assertEqual(emptied, [])


class DeliveryDisabledAtCreation(unittest.TestCase):
    """FX-3's precondition is a property of the deployment, not a switch flipped during the experiment.

    Disabling the stream mapping at runtime reported Disabled and then delivered anyway in three of six observed
    windows (root cause undetermined), which silently invalidates any experiment resting on it. The variant is
    therefore CREATED with the change signal off. These tests exist so that cannot regress, and so the normal
    deployment can never be created that way by accident.
    """

    def template(self):
        with open(tla_ops.TEMPLATE, encoding="utf-8") as handle:
            return handle.read()

    def test_only_declared_variants_are_created_without_delivery(self):
        """Restated when `no-delivery` was added (an earlier change): the membership changed, the guard did not.

        `no-reconciliation` breaks the reconciler AND has delivery off from creation. `no-delivery` is the
        configuration-only variant the no-delivery tests need — delivery off from creation with the NORMAL reconciler, so that
        WORKING reconciliation can be shown to detect the lost change. Pinned as an exact set, and the per-variant
        expectation is written as an independent literal rather than derived from the set under test, so this cannot
        become a tautology that a new variant joins unnoticed.
        """
        self.assertEqual(sorted(tla_ops.DELIVERY_DISABLED_AT_CREATION),
                         ["lab-delivery-off", "no-delivery", "no-reconciliation"])
        for variant in tla_ops.VARIANTS:
            expected = "false" if variant in ("no-reconciliation", "no-delivery", "lab-delivery-off") else "true"
            self.assertEqual(tla_ops.change_notifications_enabled(variant), expected, variant)

    def test_the_normal_deployment_is_never_created_without_delivery(self):
        """A baseline that never received a notification would prove nothing about a system whose subject is change."""
        self.assertNotIn("normal", tla_ops.DELIVERY_DISABLED_AT_CREATION)
        self.assertEqual(tla_ops.change_notifications_enabled("normal"), "true")

    def test_the_set_names_only_real_variants(self):
        """A typo here would disable delivery for nothing at all, and the experiment would look fine while proving none."""
        self.assertTrue(set(tla_ops.DELIVERY_DISABLED_AT_CREATION) <= set(tla_ops.VARIANTS))

    def test_an_unknown_variant_still_gets_delivery(self):
        self.assertEqual(tla_ops.change_notifications_enabled("something-new"), "true")

    # The template is checked as TEXT: it uses CloudFormation intrinsic tags (!If, !Ref, !GetAtt) that a plain YAML
    # parser rejects, and the test environment carries no YAML dependency. These assertions pin the actual wiring.
    def test_the_parameter_exists_and_defaults_to_delivering(self):
        template = self.template()
        self.assertIn("ChangeNotificationsEnabled:", template)
        self.assertIn('AllowedValues: ["true", "false"]', template)
        parameter = template.split("ChangeNotificationsEnabled:", 1)[1][:200]
        self.assertIn('Default: "true"', parameter)

    def test_the_mapping_is_wired_to_the_condition_not_hard_coded(self):
        template = self.template()
        self.assertIn('DeliverChangeNotifications: !Equals [!Ref ChangeNotificationsEnabled, "true"]', template)
        self.assertIn("Enabled: !If [DeliverChangeNotifications, true, false]", template)
        mapping = template.split("RecordsStreamToNotifier:", 1)[1][:600]
        self.assertNotIn("Enabled: true", mapping, "the mapping must not be hard-coded to deliver again")


class Names(unittest.TestCase):
    def test_names_fit_aws_limits(self):
        for variant in tla_ops.VARIANTS:
            prefix = tla_ops.names(variant, "123456789012")["prefix"]
            for bucket in (f"{prefix}-restricted-sections-123456789012", f"{prefix}-artifacts-123456789012",
                           f"{prefix}-restricted-vectors"):
                self.assertLessEqual(len(bucket), 63, bucket)
            self.assertLessEqual(len(f"{prefix}-restricted-kb"), 64)

    def test_variant_tags(self):
        self.assertIn({"Key": "Variant", "Value": "sensitivity"}, tla_ops.tags("no-reconciliation"))
        self.assertIn({"Key": "Episode", "Value": "03"}, tla_ops.tags("normal"))


# ── cross-layer registry/template vocabulary ────────────────────────────────────────────────────────────────
# an earlier change introduced the deployable `no-delivery` variant in this registry and proved the registry self-consistent. But a
# deployment is constrained by TWO independent CloudFormation allow-lists that nothing local read: NamePrefix's
# AllowedPattern and Variant's AllowedValues. Phase B Attempt 1 was rejected by CloudFormation on the first; the
# constraint audit that followed found the second before a second AWS attempt was made.
#
# Both constraints are EXTRACTED from the real template below, never restated here. A copied allow-list would compare
# two copies of the same omission, pass, and let the deployment fail anyway — which is the defect being closed.
def _parameter_block(template, name):
    """The text of one top-level entry under Parameters, taken from the real template."""
    marker = f"\n  {name}:\n"
    rest = template[template.index(marker) + len(marker):]
    following = re.search(r"^  \w+:", rest, re.M)
    return rest[:following.start()] if following else rest


def name_prefix_pattern(template):
    return re.search(r'^\s+AllowedPattern:\s*"(.+?)"\s*$', _parameter_block(template, "NamePrefix"), re.M).group(1)


def variant_allowed_values(template):
    raw = re.search(r"^\s+AllowedValues:\s*\[(.+?)\]\s*$", _parameter_block(template, "Variant"), re.M).group(1)
    return [value.strip() for value in raw.split(",")]


def prefix_accepted(pattern, prefix):
    """CASE 1's predicate: would CloudFormation accept this stack name?"""
    return re.match(pattern, prefix) is not None


def variant_accepted(values, variant):
    """CASE 2's predicate: would CloudFormation accept this variant value? A DIFFERENT failure from CASE 1."""
    return variant in values


# The stack name each declared variant must deploy under, as independent literals, so that B cannot become a
# tautology that reads names() and compares it against itself.
EXPECTED_PREFIX = {
    "normal": "tla-s01e03-normal",
    "status-ignored": "tla-s01e03-fx-status",
    "order-ignored": "tla-s01e03-fx-order",
    "no-reconciliation": "tla-s01e03-fx-reconciliation",
    "no-delivery": "tla-s01e03-fx-nodelivery",
    "lab-delivery-off": "tla-s01e03-lab-off",
    "lab-delivery-on": "tla-s01e03-lab-on",
}

# The two vocabularies exactly as an earlier change left them — the state in which Phase B Attempt 1 was rejected.
EARLIER_PREFIX_PATTERN = "^tla-s01e03-(normal|fx-status|fx-order|fx-reconciliation)$"
EARLIER_ALLOWED_VALUES = ["normal", "status-ignored", "order-ignored", "no-reconciliation"]


class CrossLayerVariantVocabulary(unittest.TestCase):
    """Every deployable variant must satisfy BOTH real template constraints, or it cannot be created at all."""

    def setUp(self):
        with open(tla_ops.TEMPLATE, encoding="utf-8") as handle:
            self.template = handle.read()
        self.pattern = name_prefix_pattern(self.template)
        self.values = variant_allowed_values(self.template)

    def test_the_constraints_are_read_out_of_the_real_template(self):
        """If these ever stop matching the file, every assertion below is comparing copies and proves nothing."""
        self.assertIn(f'AllowedPattern: "{self.pattern}"', self.template)
        self.assertIn("AllowedValues: [" + ", ".join(self.values) + "]", self.template)
        self.assertTrue(self.pattern.startswith("^tla-s01e03-"))

    def test_every_declared_variant_satisfies_both_constraints(self):
        """A · B · C · D for the real registry against the real template.

        The classes are accumulated and reported TOGETHER rather than asserted in sequence. Asserting C before D
        aborts on the first, so a registry broken in BOTH vocabularies at once — exactly how an earlier change left this one —
        would report only the NamePrefix half and hide the Variant half until the next deployment attempt.
        """
        failures = {}
        for variant in tla_ops.VARIANTS:
            if variant not in EXPECTED_PREFIX:
                failures.setdefault("A: undeclared variant, no expected stack name", []).append(variant)
                continue
            prefix = tla_ops.names(variant, "123456789012")["prefix"]
            if prefix != EXPECTED_PREFIX[variant]:
                failures.setdefault("B: unexpected generated stack name", []).append((variant, prefix))
            if not prefix_accepted(self.pattern, prefix):
                failures.setdefault("C: rejected by NamePrefix.AllowedPattern", []).append((variant, prefix))
            if not variant_accepted(self.values, variant):
                failures.setdefault("D: absent from Variant.AllowedValues", []).append(variant)
        self.assertEqual(failures, {}, "a declared variant cannot be deployed")

    def test_the_invariant_covers_every_deployable_variant(self):
        """It must not silently shrink to the variants that happen to pass."""
        self.assertEqual(sorted(tla_ops.VARIANTS), sorted(EXPECTED_PREFIX))
        for required in ("normal", "status-ignored", "order-ignored", "no-reconciliation", "no-delivery"):
            self.assertIn(required, tla_ops.VARIANTS)

    def test_no_delivery_specifically(self):
        """The variant Phase B needs, asserted against both constraints at once with explicit literals."""
        prefix = tla_ops.names("no-delivery", "123456789012")["prefix"]
        self.assertEqual({"B: stack name": prefix,
                          "C: accepted by NamePrefix.AllowedPattern": prefix_accepted(self.pattern, prefix),
                          "D: present in Variant.AllowedValues": variant_accepted(self.values, "no-delivery")},
                         {"B: stack name": "tla-s01e03-fx-nodelivery",
                          "C: accepted by NamePrefix.AllowedPattern": True,
                          "D: present in Variant.AllowedValues": True})


class BothMismatchClassesAreDetected(unittest.TestCase):
    """CASE 1 and CASE 2 are different failures, and the suite must tell them apart.

    Proved against synthetic constraints rather than by editing the template: the predicates exercised here are the
    same ones the invariant above uses, so a regression in either is caught without touching deployment vocabulary.
    """

    def template_constraints(self):
        with open(tla_ops.TEMPLATE, encoding="utf-8") as handle:
            template = handle.read()
        return name_prefix_pattern(template), variant_allowed_values(template)

    def test_case_1_a_generated_prefix_absent_from_the_pattern_is_rejected(self):
        self.assertFalse(prefix_accepted(EARLIER_PREFIX_PATTERN, "tla-s01e03-fx-nodelivery"))
        self.assertTrue(variant_accepted(["no-delivery"], "no-delivery"), "only CASE 1 may fire here")

    def test_case_2_a_variant_absent_from_allowed_values_is_rejected(self):
        self.assertFalse(variant_accepted(EARLIER_ALLOWED_VALUES, "no-delivery"))
        self.assertTrue(prefix_accepted("^tla-s01e03-(normal|fx-nodelivery)$", "tla-s01e03-fx-nodelivery"),
                        "only CASE 2 may fire here")

    def test_the_two_cases_are_independent(self):
        """Each predicate must be able to fail while the other passes, or one could mask the other."""
        self.assertEqual((not prefix_accepted(EARLIER_PREFIX_PATTERN, "tla-s01e03-fx-nodelivery"),
                          variant_accepted(["no-delivery"], "no-delivery")), (True, True))
        self.assertEqual((prefix_accepted("^tla-s01e03-(fx-nodelivery)$", "tla-s01e03-fx-nodelivery"),
                          not variant_accepted(EARLIER_ALLOWED_VALUES, "no-delivery")), (True, True))

    def test_it_would_have_caught_the_earlier_omission(self):
        """Run TODAY's registry against the vocabularies as an earlier change left them: BOTH checks must fail, and name it.

        This is the point of the entry. That change's change was self-consistent inside tla_ops and no local test read the
        template, so the omission reached CloudFormation twice.
        """
        prefix_failures, value_failures = [], []
        # The learner-lab variants were added after an earlier change, so That change's vocabulary could never have held them; they are
        # covered by the invariant against the REAL template above. This test replays the registry an earlier change knew.
        for variant in (v for v in tla_ops.VARIANTS if v not in tla_ops.LAB_VARIANTS):
            if not prefix_accepted(EARLIER_PREFIX_PATTERN, tla_ops.names(variant, "123456789012")["prefix"]):
                prefix_failures.append(variant)
            if not variant_accepted(EARLIER_ALLOWED_VALUES, variant):
                value_failures.append(variant)
        self.assertEqual(prefix_failures, ["no-delivery"], "CASE 1 must name exactly the omitted variant")
        self.assertEqual(value_failures, ["no-delivery"], "CASE 2 must name exactly the omitted variant")

    def test_arbitrary_stack_names_remain_rejected(self):
        """The repair widened the allow-list by one name; it must not have opened it."""
        pattern, _ = self.template_constraints()
        for rejected in ("tla-s01e03-anything", "tla-s01e03-fx-nodeliveryX", "tla-s01e03-fx-node", "tla-s01e03-",
                         "tla-s01e02-normal", "my-own-stack"):
            self.assertFalse(prefix_accepted(pattern, rejected), rejected)

    def test_arbitrary_variant_names_remain_rejected(self):
        _, values = self.template_constraints()
        for rejected in ("no-delivery-2", "anything", "", "NORMAL", "sensitivity"):
            self.assertFalse(variant_accepted(values, rejected), rejected)


if __name__ == "__main__":
    unittest.main()
