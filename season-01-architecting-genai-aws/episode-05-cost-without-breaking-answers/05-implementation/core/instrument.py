#!/usr/bin/env python3
"""PUBLISHABLE CORE — consumption meter.

Two categories, because the whole point of the lab is that they are different things:

    ORIGINAL      work the request performs
    PRESERVATION  work an optimisation ADDS so it is allowed to reuse anything

Counts of operations only. No prices. This lab does not price anything.
"""
ORIGINAL, PRESERVATION = "ORIGINAL", "PRESERVATION"

CATEGORY = {
    "retrieval_calls": ORIGINAL, "context_sections": ORIGINAL, "generation_calls": ORIGINAL,
    "authority_confirmations": ORIGINAL,
    "metadata_writes": PRESERVATION, "equivalence_checks": PRESERVATION,
    "invalidation_events": PRESERVATION,
}


class Meter:
    def __init__(self):
        self.c = {}

    def add(self, driver, n=1):
        if driver not in CATEGORY:
            raise KeyError(f"unknown cost driver {driver!r}")
        self.c[driver] = self.c.get(driver, 0) + n

    def by_category(self):
        out = {ORIGINAL: {}, PRESERVATION: {}}
        for k, v in self.c.items():
            out[CATEGORY[k]][k] = v
        return out

    def consumption(self):
        return dict(self.c)
