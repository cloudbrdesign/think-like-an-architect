"""Build-time re-measurement of the constraint size the platform accepts (TST-SCALE-001 support, privileged).

OBSERVED PLATFORM BEHAVIOUR UNDER THE TESTED CONDITIONS — NOT AN ARCHITECTURAL CONSTANT.

Shared-tier constraints with a growing number of domain grants (the only relevant grant, FIN-REPORTING, always last so
truncation would show) are sent directly to the shared knowledge base with operator credentials. Bisection finds the
largest grant count the service accepts, for two identifier lengths, and records the service's own error messages.
The application's safety budget (core/constraints.py) must stay below what is measured here.
"""
import json

from harness import canaries
from core import constraints

PREFIXES = ("SYN-PROBE-", "SYN-LONGER-PROBE-IDENTIFIER-")


def _filter(prefix, count):
    domains = [f"{prefix}{i:04d}" for i in range(count)] + ["FIN-REPORTING"]
    return {"orAll": [{"equals": {"key": "label", "value": "INTERNAL"}},
                      {"andAll": [{"equals": {"key": "label", "value": "CONFIDENTIAL"}},
                                  {"in": {"key": "scope", "value": domains}}]}]}


def probe(target, prefix, count):
    kb, _ = target.knowledge_base("shared")
    retrieval_filter = _filter(prefix, count)
    entry = {"prefix": prefix, "grants": count + 1, "default_bytes": constraints.serialized_bytes(retrieval_filter),
             "compact_bytes": len(json.dumps(retrieval_filter, separators=(",", ":")))}
    try:
        response = target.client("bedrock-agent-runtime").retrieve(
            knowledgeBaseId=kb, retrievalQuery={"text": canaries.questions()["finance"]["text"]},
            retrievalConfiguration={"vectorSearchConfiguration": {"numberOfResults": 5, "filter": retrieval_filter}})
        keys = [f"{r['metadata'].get('document_id')}-{r['metadata'].get('section_id')}" for r in response["retrievalResults"]]
        entry.update(accepted=True, last_grant_honoured="D-08-S1" in keys)
    except Exception as error:  # noqa: BLE001 — the service's message is the observation
        message = str(error)
        entry.update(accepted=False, layer="S3Vectors" if "S3Vectors" in message else "Retrieve",
                     message=message.split(": ", 1)[-1][:160])
    return entry


def measure(target):
    series, boundaries = [], {}
    for prefix in PREFIXES:
        low, high = 1, 1200
        low_entry, high_entry = probe(target, prefix, low), probe(target, prefix, high)
        series += [low_entry, high_entry]
        if not low_entry["accepted"] or high_entry["accepted"]:
            boundaries[prefix] = {"error": "bisection endpoints did not bracket the limit", "low": low_entry, "high": high_entry}
            continue
        while high - low > 1:
            middle = (low + high) // 2
            entry = probe(target, prefix, middle)
            series.append(entry)
            if entry["accepted"]:
                low, low_entry = middle, entry
            else:
                high, high_entry = middle, entry
        boundaries[prefix] = {"largest_accepted": low_entry, "smallest_rejected": high_entry}
    accepted = [e for e in series if e["accepted"]]
    return {"note": __doc__.strip().splitlines()[2], "series": series, "boundaries": boundaries,
            "all_accepted_honoured_last_grant": all(e["last_grant_honoured"] for e in accepted),
            "distinct_rejections": sorted({f"{e['layer']}: {e['message']}" for e in series if not e["accepted"]}),
            "application_budget_bytes_default_separators": constraints.CONSTRAINT_BUDGET_BYTES}
