"""The generated oracle must agree with the hand-written expectations (SYNTHETIC_DATA_MODEL.md §3) — no AWS."""
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from harness import canaries, common  # noqa: E402

MODEL = os.path.join(common.EPISODE, "03-architecture", "SYNTHETIC_DATA_MODEL.md")
PERSONAS = [f"P-{i:02d}" for i in range(1, 11)]
# Sections the hand-written table does not list, with the expectation stated here explicitly.
NOT_IN_HAND_TABLE = {"D-13-S1": "INTERNAL before reclassification (TST-CHG-002): eligible exactly like other INTERNAL sections"}


def hand_table():
    with open(MODEL, encoding="utf-8") as handle:
        text = handle.read()
    part = text.split("## 3. Expected eligibility", 1)[1].split("\n---", 1)[0]
    rows = {}
    for line in part.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) != 11 or cells[0] in ("Section", "---") or set(cells[1]) <= {"-"}:
            continue
        refs = re.findall(r"D-\d{2}(?: §\d(?:–\d)?)?", cells[0])
        rows[cells[0]] = (refs, dict(zip(PERSONAS, [c == "✓" for c in cells[1:]])))
    return rows


def expand(ref, oracle):
    match = re.match(r"(D-\d{2})(?: §(\d)(?:–(\d))?)?$", ref)
    document, first, last = match.group(1), match.group(2), match.group(3)
    if first is None:
        return sorted(k for k in oracle if k.startswith(document + "-"))
    return [f"{document}-S{n}" for n in range(int(first), int(last or first) + 1)]


class OracleCrossCheck(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.oracle = canaries.oracle()
        cls.table = hand_table()

    def test_hand_table_parsed(self):
        self.assertEqual(len(self.table), 8)

    def test_every_hand_written_expectation_matches_the_generated_oracle(self):
        covered = set()
        for name, (refs, expected) in self.table.items():
            for ref in refs:
                for key in expand(ref, self.oracle):
                    covered.add(key)
                    generated = {p: p in self.oracle[key]["eligible"] for p in PERSONAS}
                    self.assertEqual(generated, expected, f"{key} (row: {name})")
        self.assertEqual(sorted(set(self.oracle) - covered), sorted(NOT_IN_HAND_TABLE))

    def test_sections_outside_the_hand_table_are_stated_explicitly(self):
        internal = self.oracle["D-01-S1"]["eligible"]
        self.assertEqual(self.oracle["D-13-S1"]["eligible"], internal)

    def test_every_section_has_a_unique_canary(self):
        found = [e["canary"] for e in self.oracle.values()]
        self.assertEqual(len(found), len(set(found)))
        self.assertEqual(len(found), 22)

    def test_expected_inventory(self):
        inventory = canaries.expected_inventory(self.oracle)
        self.assertEqual(inventory["restricted"], ["D-04-S2", "D-05-S1"])
        self.assertEqual(inventory["nowhere"], ["D-04-S3", "D-09-S1", "D-10-S1", "D-11-S1", "D-15-S1"])
        self.assertEqual(len(inventory["shared"]), 15)
        self.assertEqual((self.oracle["D-14-S1"]["label"], self.oracle["D-14-S1"]["scope"]), ("CONFIDENTIAL", "BID-ORION"))

    def test_over_limit_persona_holds_fin_reporting_but_is_never_in_the_hand_table(self):
        self.assertIn("P-11", self.oracle["D-08-S1"]["eligible"])     # eligible by the rule; refused by CTL-013
        self.assertEqual(len(canaries.personas()["P-11"]["domains"]), 1000)


if __name__ == "__main__":
    unittest.main()
