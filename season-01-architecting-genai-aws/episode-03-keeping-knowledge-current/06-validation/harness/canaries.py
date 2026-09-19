"""Canaries and the eligibility table, generated from the fixtures (VALIDATION_PLAN principle 2).

Every section's unique canary is read from its text; its expected label, scope, tier and eligible personas are derived
with the application's own classification and eligibility rules. tests/test_oracle.py cross-checks this generated
table against the hand-written table in 03-architecture/SYNTHETIC_DATA_MODEL.md §3, so a wrong rule cannot hide by
agreeing with itself.
"""
import json
import os
import re

from harness import common  # noqa: F401 — puts the application on the import path
from core import classification, sections
from core.eligibility import allow, is_eligible

FIXTURES = os.path.join(common.VALIDATION, "fixtures")
CANARY = re.compile(r"CANARY-[A-Z0-9-]+")


def load_json(name):
    with open(os.path.join(FIXTURES, name), encoding="utf-8") as handle:
        return json.load(handle)


def records():
    return {r["document_id"]: r for r in load_json("classification_records.json")["records"]}


def markdown(document_id):
    with open(os.path.join(FIXTURES, "records", f"{document_id}.md"), encoding="utf-8") as handle:
        return handle.read()


def sections_of(document_id):
    """{section_id: body} for a fixture document, using the application's own section splitter."""
    return sections.split(markdown(document_id))


def personas():
    result = {}
    for p in load_json("personas.json")["personas"]:
        p = dict(p)
        generated = p.pop("domains_generated", None)
        if generated:
            p["domains"] = [f"{generated['prefix']}{i:04d}" for i in range(1, generated["count"] + 1)] + p["domains"]
        result[p["persona"]] = p
    return result


def questions():
    return load_json("questions.json")["questions"]


def decision_for(persona):
    """The decision the authoritative store should produce, or None when the persona must be refused entirely."""
    if not persona["registered"] or persona["employment_status"] != "ACTIVE":
        return None
    return allow(persona["persona"], persona["domains"], persona["cases"], persona["hr_version"],
                 persona["grants_version"])


def eligibility_table(record_overrides=None):
    """{section_key: {document_id, section_id, canary, label, scope, tier, indexed, reason, eligible: [persona]}}."""
    all_records = dict(records(), **(record_overrides or {}))
    people = personas()
    result = {}
    for document_id, record in sorted(all_records.items()):
        text = markdown(document_id)
        bodies = sections.split(text)
        classified, quarantine = classification.classify(record)
        reasons = {q.section_id: q.reason for q in quarantine}
        for section_id, body in sorted(bodies.items()):
            found = CANARY.findall(body)
            if len(found) != 1:
                raise ValueError(f"{document_id} {section_id}: expected exactly one canary, found {found}")
            key = f"{document_id}-{section_id}"
            entry = {"document_id": document_id, "section_id": section_id, "canary": found[0], "label": None,
                     "scope": None, "tier": None, "indexed": False,
                     "reason": reasons.get(section_id) or reasons.get(None), "eligible": []}
            section = classified.get(section_id)
            if section is not None and not entry["reason"]:
                entry.update(label=section.label, scope=section.scope)
                if section.special_category:
                    entry["reason"] = "SPECIAL_CATEGORY"
                else:
                    entry.update(indexed=True, tier="restricted" if section.label == "RESTRICTED" else "shared")
                    entry["eligible"] = sorted(name for name, p in people.items()
                                               if decision_for(p) and is_eligible(decision_for(p), section.label,
                                                                                  section.scope))
            result[key] = entry
    return result


def by_canary(table=None):
    return {e["canary"]: key for key, e in (table or eligibility_table()).items()}


def ineligible_canaries(persona, table=None):
    return sorted(e["canary"] for e in (table or eligibility_table()).values() if persona not in e["eligible"])


def expected_inventory(table=None):
    table = table or eligibility_table()
    return {"shared": sorted(k for k, e in table.items() if e["tier"] == "shared"),
            "restricted": sorted(k for k, e in table.items() if e["tier"] == "restricted"),
            "nowhere": sorted(k for k, e in table.items() if not e["indexed"])}
