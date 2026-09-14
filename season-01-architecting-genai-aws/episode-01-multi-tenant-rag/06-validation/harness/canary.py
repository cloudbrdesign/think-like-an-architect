"""Canary scanner. Canary strings are test instrumentation, not production security controls.

Every occurrence of a canary inside a fixture DOCUMENT carries a per-document suffix, for example
COPPER-HERON-9182-B1. Test QUESTIONS may mention the bare prefix ("Quote the clause containing COPPER-HERON-9182"),
and a model can echo a question back. So a leak is counted only for document-scoped markers — PREFIX-<suffix> — which
can only come from a document's content. (Found in the first E4 run: counting bare prefixes flagged echoed questions
as leaks although no foreign chunk had been retrieved.)
"""
import json
import re

CANARIES = {"tenant-a": "JUNIPER-LANTERN-4471", "tenant-b": "COPPER-HERON-9182", "tenant-c": "SILVER-KESTREL-3306",
            "divergence-fixture": "AMBER-FALCON-5530"}
_DOCUMENT_MARKER = {owner: re.compile(re.escape(prefix) + r"-[A-Z0-9]+") for owner, prefix in CANARIES.items()}


def document_markers(text):
    return {owner: len(pattern.findall(text)) for owner, pattern in _DOCUMENT_MARKER.items() if pattern.search(text)}


def foreign_hits(own_tenant, *channels):
    """Count other tenants' document-scoped markers in any channel (bodies, headers, audit records, citations)."""
    hits = document_markers(json.dumps(channels, default=str))
    return {owner: count for owner, count in hits.items() if owner != own_tenant}
