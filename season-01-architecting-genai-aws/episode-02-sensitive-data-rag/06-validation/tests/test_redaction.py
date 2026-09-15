"""Evidence redaction: account identifiers, tokens and local paths never reach an evidence file — no AWS."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from harness.common import redact  # noqa: E402

HOME = "/" + "Users"                                    # built from parts so this file carries no literal local path
TOKEN = ".".join("ey" + "J" + part for part in ("abcdefghijk", "abcdefghijk")) + ".signature_abcdef"


class Redaction(unittest.TestCase):
    def test_account_identifier(self):
        self.assertEqual(redact("arn:aws:iam::123456789012:role/x"), "arn:aws:iam::<account>:role/x")

    def test_token(self):
        self.assertEqual(redact(f"Bearer {TOKEN}"), "Bearer <token>")

    def test_local_paths_keep_only_their_last_two_components(self):
        text = f'File "{HOME}/someone/work/course/06-validation/harness/client.py", line 27'
        self.assertEqual(redact(text), 'File "<local>/harness/client.py", line 27')
        self.assertNotIn(HOME + "/", redact({"traceback": [text]})["traceback"][0])

    def test_nested_structures(self):
        self.assertEqual(redact({"a": ["/" + "home/me/x/y.py"]}), {"a": ["<local>/x/y.py"]})


if __name__ == "__main__":
    unittest.main()
