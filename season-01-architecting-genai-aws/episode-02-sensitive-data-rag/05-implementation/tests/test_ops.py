"""Deployment script guards (no AWS): normal builds carry no failure-experiment code; each variant replaces exactly one
module; variants deploy only through the experiment runner; resource names fit AWS limits."""
import argparse
import json
import os
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
        for function in ("query", "ingestion"):
            for name, text in self.package("normal", function).items():
                self.assertNotIn(MARKER, text, name)

    def test_each_variant_replaces_exactly_one_module(self):
        for variant, (_, (module, _)) in ((v, spec) for v, spec in tla_ops.VARIANTS.items() if spec[1]):
            manifest = self.build(variant)
            self.assertEqual(manifest["replaced_modules"], [module])
            function = "ingestion" if module == "core/sections.py" else "query"
            self.assertIn(MARKER, self.package(variant, function)[module])

    def test_guard_refuses_variant_code_in_a_normal_build(self):
        staging = tla_ops._stage("normal")
        with open(os.path.join(staging, "core", "constraints.py"), "a", encoding="utf-8") as handle:
            handle.write(f"\n# {MARKER}\n")
        with self.assertRaises(SystemExit):
            tla_ops._guard("normal", staging)

    def test_packages_contain_only_their_function(self):
        self.build("normal")
        self.assertFalse(any(n.startswith("ingestion/") for n in self.package("normal", "query")))
        self.assertFalse(any(n.startswith("query/") for n in self.package("normal", "ingestion")))
        self.assertIn('VARIANT = "normal"', self.package("normal", "query")["adapters/build_info.py"])

    def test_variant_deploy_refused_outside_the_runner(self):
        self.build("eligibility-removed")
        os.environ.pop("TLA_SENSITIVITY_RUN", None)
        with self.assertRaises(SystemExit) as refused:
            tla_ops.cmd_deploy(argparse.Namespace(variant="eligibility-removed"))
        self.assertIn("experiment runner", str(refused.exception))


class Names(unittest.TestCase):
    def test_names_fit_aws_limits(self):
        for variant in tla_ops.VARIANTS:
            prefix = tla_ops.names(variant, "123456789012")["prefix"]
            for bucket in (f"{prefix}-restricted-sections-123456789012", f"{prefix}-artifacts-123456789012",
                           f"{prefix}-restricted-vectors"):
                self.assertLessEqual(len(bucket), 63, bucket)
            self.assertLessEqual(len(f"{prefix}-restricted-kb"), 64)

    def test_variant_tags(self):
        self.assertIn({"Key": "Variant", "Value": "sensitivity"}, tla_ops.tags("claims-as-grants"))
        self.assertIn({"Key": "Episode", "Value": "02"}, tla_ops.tags("normal"))


if __name__ == "__main__":
    unittest.main()
