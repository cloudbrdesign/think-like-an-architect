"""Fixture tests for the education-mode boundary check.

Every planted violation is built at runtime inside a temporary directory, so this repository never contains a real
commercial marker, canary, secret or local path. Each check must be SEEN TO FAIL on its planted violation.
Test IDs follow the G1 cross-repository safety tests: A (valid fixture accepted), B (planted violations rejected),
F (education CI needs no commercial access).
"""
import json
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.dirname(HERE))
import boundary_check as bc  # noqa: E402

with open(os.path.join(REPO_ROOT, ".tla", "boundary.json"), encoding="utf-8") as handle:
    CONFIG = json.load(handle)

VALID = {
    "README.md": "# Fixture\n\nSee [templates](templates/README.md).\n",
    "LICENSING.md": "No licence yet.\n",
    "CONTRIBUTING.md": "Branches and pull requests.\n",
    ".github/CODEOWNERS": "* @example\n",
    ".github/pull_request_template.md": "## What changed?\n",
    ".github/workflows/ci.yml": "permissions: {}\nenv:\n  T: ${{ secrets.GITHUB_TOKEN }}\n",
    "templates/README.md": "Templates.\n",
    "season-01-architecting-genai-aws/README.md": "Season 1.\n",
}


class EducationBoundary(unittest.TestCase):
    def run_scan(self, extra=None, drop=()):
        files = dict(VALID)
        files.update(extra or {})
        for key in drop:
            files.pop(key)
        root = tempfile.mkdtemp(prefix="tla-edu-fixture-")
        self.addCleanup(shutil.rmtree, root)
        for rel, content in files.items():
            path = os.path.join(root, rel)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(content)
        return bc.scan(root, CONFIG)

    def assertRejected(self, extra=None, drop=(), expect=""):
        violations = self.run_scan(extra, drop)
        self.assertTrue(violations, "planted violation was NOT detected")
        if expect:
            self.assertTrue(any(expect in v for v in violations), violations)

    # A — valid educational fixture is accepted
    def test_A_valid_education_fixture_passes(self):
        self.assertEqual(self.run_scan(), [])

    # B — planted commercial markers, paths and leaks are rejected
    def test_B_commercial_marker_rejected(self):
        self.assertRejected({"templates/brief.md": "header " + bc.MARKER + "\n"}, expect="commercial marker")

    def test_B_spdx_commercial_identifier_rejected(self):
        self.assertRejected({"templates/brief.md": "SPDX-License-Identifier: " + bc.SPDX_MARKER + "\n"},
                            expect="commercial marker")

    def test_B_canary_token_rejected(self):
        self.assertRejected({"templates/notes.txt": "tla-canary-" + "a1" * 16 + "\n"}, expect="canary")

    def test_B_canary_file_path_rejected(self):
        self.assertRejected({".tla-commercial-canary": "x\n"}, expect="forbidden path")

    def test_B_customer_package_manifest_rejected(self):
        self.assertRejected({"season-01-architecting-genai-aws/package.manifest.yaml": "files: []\n"},
                            expect="forbidden path")

    def test_B_release_evidence_rejected(self):
        self.assertRejected({"season-01-architecting-genai-aws/release-evidence/r.json": "{}\n"},
                            expect="forbidden path")

    def test_B_submodule_rejected(self):
        self.assertRejected({".gitmodules": "[submodule \"x\"]\n"}, expect="forbidden path")

    def test_B_unknown_top_level_rejected(self):
        self.assertRejected({"production/main.tf": "# x\n"}, expect="not allowlisted")

    def test_B_commercial_repository_reference_rejected(self):
        self.assertRejected({"README.md": "clone " + bc.PROD_NAME + "\n"}, expect="commercial repository")

    def test_B_local_filesystem_path_rejected(self):
        self.assertRejected({"templates/p.md": "see /Us" + "ers/someone/project/file\n"}, expect="local filesystem")

    def test_B_secret_rejected(self):
        self.assertRejected({"templates/k.md": "key " + "AK" + "IA" + "ABCDEFGHIJKLMNOP" + "\n"}, expect="secret")

    def test_B_broken_relative_link_rejected(self):
        self.assertRejected({"templates/l.md": "[missing](nowhere.md)\n"}, expect="broken relative link")

    def test_B_missing_required_file_rejected(self):
        self.assertRejected(drop=("LICENSING.md",), expect="required file missing")

    # F — education CI must not need commercial access
    def test_F_workflow_checking_out_another_repository_rejected(self):
        workflow = "steps:\n  - uses: actions/checkout@v0\n    with:\n      repository: someone/private-source\n"
        self.assertRejected({".github/workflows/ci.yml": workflow}, expect="another repository")

    def test_F_workflow_using_non_default_secret_rejected(self):
        workflow = "env:\n  T: ${{ secrets." + "COMMERCIAL_TOKEN }}\n"
        self.assertRejected({".github/workflows/ci.yml": workflow}, expect="secrets.COMMERCIAL_TOKEN")


if __name__ == "__main__":
    unittest.main()
