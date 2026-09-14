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
