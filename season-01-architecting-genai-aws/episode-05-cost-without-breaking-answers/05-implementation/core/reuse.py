#!/usr/bin/env python3
"""PUBLISHABLE CORE — ONE safe reuse mode: retain the generated answer.

The rules this implements are NOT Episode 05's inventions. They are inherited:

  * only provably INTERNAL-only results are retained          (confinement)
  * the contributing SECTION SET is carried with the answer    (what it was built from)
  * on EVERY serve, EVERY carried section is re-checked for
    current eligibility and current document state             (no per-answer shortcut)

The last rule is the expensive one and it is the one that makes reuse legal. A design that checked
only the first carried section would serve a withdrawn step the moment a later one was withdrawn.

There is deliberately no way to switch these checks off here. The version used to demonstrate what
happens without them is an internal, instructor-only test artefact and is NOT part of this core.
"""
from . import corpus


class ReuseStore:
    """Retains a completed answer. On a hit, retrieval AND generation are avoided."""

    def __init__(self):
        self.store = {}
        self.hits = self.misses = self.refused = self.not_retained = 0

    @staticmethod
    def key(question):
        return ("INTERNAL", question)

    def retain(self, question, sections, text, meter):
        if not sections or not all(s.label == corpus.INTERNAL for s in sections):
            self.not_retained += 1            # confinement: mixed or sensitive answers are never kept
            return False
        meter.add("metadata_writes")          # carriage is PRESERVATION work
        self.store[self.key(question)] = {
            "sections": [s.section_id for s in sections],
            "currency_basis": {s.doc_id: corpus.DOCUMENTS[s.doc_id].version for s in sections},
            "text": text}
        return True

    def serve(self, question, principal, meter):
        rec = self.store.get(self.key(question))
        if rec is None:
            self.misses += 1
            return None
        meter.add("equivalence_checks")
        for sid in rec["sections"]:
            s = corpus.SECTIONS[sid]
            if not corpus.eligible(principal, s):
                self.refused += 1
                return {"served": False, "reason": "entitlement no longer permits a carried section",
                        "section": sid}
            meter.add("authority_confirmations")     # EVERY carried section, EVERY serve
            if not corpus.in_force(s):
                self.refused += 1
                return {"served": False, "reason": "a carried section is no longer in force",
                        "section": sid}
        self.hits += 1
        return {"served": True, "text": rec["text"], "sections": rec["sections"], "reason": "reused"}
