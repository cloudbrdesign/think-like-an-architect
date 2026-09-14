"""Component tests of the deployment tooling's safety and reproducibility rules (standard library only)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "05-implementation", "scripts")))

import tla_ops  # noqa: E402


class NoSuchBucket(Exception):
    pass


class FakeS3:
    """A bucket re-created soon after deletion: configuration calls briefly report NoSuchBucket (seen in the E4 fresh-copy run)."""

    def __init__(self, transient_failures=2):
        self.transient_failures, self.calls = transient_failures, []

    def head_bucket(self, Bucket):
        raise NoSuchBucket("404")

    def create_bucket(self, Bucket):
        self.calls.append("create_bucket")

    def _config(self, name):
        self.calls.append(name)
        if self.transient_failures:
            self.transient_failures -= 1
            raise NoSuchBucket("The specified bucket does not exist")

    def put_public_access_block(self, **kwargs):
        self._config("put_public_access_block")

    def put_bucket_policy(self, **kwargs):
        self._config("put_bucket_policy")

    def put_bucket_tagging(self, **kwargs):
        self._config("put_bucket_tagging")


class ArtifactBucketTests(unittest.TestCase):
    def test_transient_no_such_bucket_after_recreation_is_retried(self):
        s3 = FakeS3(transient_failures=2)
        tla_ops._ensure_artifact_bucket(s3, "tla-s01e01-normal-artifacts-x", "normal", sleep=lambda _: None)
        self.assertEqual(s3.calls.count("put_public_access_block"), 3)
        self.assertIn("put_bucket_policy", s3.calls)
        self.assertIn("put_bucket_tagging", s3.calls)

    def test_retry_is_bounded(self):
        s3 = FakeS3(transient_failures=100)
        with self.assertRaises(NoSuchBucket):
            tla_ops._ensure_artifact_bucket(s3, "b", "normal", sleep=lambda _: None)

    def test_non_transient_errors_are_not_retried(self):
        calls = []

        def denied():
            calls.append(1)
            raise PermissionError("AccessDenied")
        with self.assertRaises(PermissionError):
            tla_ops._retry_transient(denied, sleep=lambda _: None)
        self.assertEqual(len(calls), 1)


class FakeBedrock:
    def __init__(self, states=None, error=None):
        self.states, self.error, self.asked = states or {}, error, []

    def get_foundation_model_availability(self, modelId):
        self.asked.append(modelId)
        if self.error:
            raise self.error
        return self.states.get(modelId, {"authorizationStatus": "AUTHORIZED", "entitlementAvailability": "AVAILABLE",
                                         "regionAvailability": "AVAILABLE"})


class ModelAccessPreflightTests(unittest.TestCase):
    """VE-18 failure paths (the success path is proven in the real sandbox run)."""

    def check(self, bedrock, region="us-east-1"):
        return tla_ops.model_access_problems(bedrock, region, report=lambda _: None)

    def test_both_required_models_are_checked_and_pass(self):
        bedrock = FakeBedrock()
        self.assertEqual(self.check(bedrock), [])
        self.assertEqual(bedrock.asked, ["amazon.titan-embed-text-v2:0", "amazon.nova-micro-v1:0"])

    def test_model_access_not_granted_is_named_with_an_actionable_message(self):
        bedrock = FakeBedrock({"amazon.nova-micro-v1:0": {"authorizationStatus": "NOT_AUTHORIZED",
                                                          "entitlementAvailability": "AVAILABLE", "regionAvailability": "AVAILABLE"}})
        problems = self.check(bedrock)
        self.assertEqual(len(problems), 1)
        self.assertIn("amazon.nova-micro-v1:0", problems[0])
        self.assertIn("Model access", problems[0])
        self.assertIn("scripts/preflight.sh", problems[0])

    def test_model_not_available_in_region_fails_without_substitution(self):
        bedrock = FakeBedrock({"amazon.titan-embed-text-v2:0": {"authorizationStatus": "AUTHORIZED",
                                                                "entitlementAvailability": "AVAILABLE", "regionAvailability": "NOT_AVAILABLE"}})
        problems = self.check(bedrock, region="eu-west-2")
        self.assertIn("amazon.titan-embed-text-v2:0", problems[0])
        self.assertIn("will not substitute", problems[0])
        self.assertEqual(bedrock.asked, list(tla_ops.MODELS))  # only the approved models are ever considered

    def test_unreadable_availability_fails_closed(self):
        problems = self.check(FakeBedrock(error=PermissionError("AccessDenied")))
        self.assertEqual(len(problems), 2)
        self.assertTrue(all("GetFoundationModelAvailability" in p for p in problems))

    def test_template_uses_only_the_approved_in_region_model(self):
        template = open(tla_ops.TEMPLATE, encoding="utf-8").read()
        self.assertEqual(sorted(set(__import__("re").findall(r"GENERATION_MODEL_ID:\s*(\S+)", template))), ["amazon.nova-micro-v1:0"])
        self.assertIn("foundation-model/amazon.titan-embed-text-v2:0", template)


class NamingAndTaggingTests(unittest.TestCase):
    def test_variant_names_and_standard_tags(self):
        names = tla_ops.names("sensitivity", "123456789012")
        self.assertEqual(names["stack"], "tla-s01e01-sensitivity")
        tags = {t["Key"]: t["Value"] for t in tla_ops.tags("sensitivity")}
        self.assertEqual(tags, {"Project": "CloudBreweryLabs", "Course": "ThinkLikeAnArchitect", "Season": "01",
                                "Episode": "01", "Environment": "Sandbox", "ManagedBy": "CloudBreweryLabs",
                                "Variant": "sensitivity", "Purpose": "education", "DeployedWith": "CloudFormation"})


if __name__ == "__main__":
    unittest.main()
