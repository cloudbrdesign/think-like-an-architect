"""Audit export and usage summary, taken before a deployment is destroyed (COST_AND_CLEANUP cleanup step 1).

The audit records are content-free by design, so they can be kept as evidence. The usage summary counts what drives
cost — requests, knowledge-base searches, model tokens, ingested sections — and prices it with the dated figures in
05-implementation/COST_AND_CLEANUP.md. It is an estimate from observed volumes, not a bill.
"""
import json
import os

from harness.common import RESULTS, redact
from harness.observe import Observer

PRICES_USD = {"nova_micro_input_per_million": 0.08, "nova_micro_output_per_million": 0.24,
              "vector_queries_per_million": 2.50, "titan_embeddings_per_million_tokens": 0.02,
              "http_api_requests_per_million": 1.00, "lambda_requests_per_million": 0.20}
PRICES_DATE = "2026-09-14 (public AWS pricing pages, US East; not re-read)"


def export_audit(target, run_id):
    items = Observer(target).audit_items()
    directory = os.path.join(RESULTS, run_id)
    os.makedirs(directory, exist_ok=True)
    with open(os.path.join(directory, "audit.jsonl"), "w", encoding="utf-8") as handle:
        for item in sorted(items, key=lambda i: (i.get("timestamp") or "", i["request_id"])):
            handle.write(json.dumps(redact(item), sort_keys=True, default=str) + "\n")
    summary = summarise(items, target.stack_name)
    with open(os.path.join(directory, "usage-summary.json"), "w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2, sort_keys=True)
    return summary


def summarise(items, deployment):
    queries = [i for i in items if i.get("record_type") == "QUERY"]
    ingestions = [i for i in items if i.get("record_type") == "INGESTION_REPORT"]
    searches = sum(len(i.get("tiers_called") or []) for i in queries)
    generated = [i for i in queries if (i.get("generation") or {}).get("invoked")]
    tokens_in = sum(int((i.get("generation") or {}).get("input_tokens") or 0) for i in generated)
    tokens_out = sum(int((i.get("generation") or {}).get("output_tokens") or 0) for i in generated)
    sections = sum(len(v) for r in ingestions for v in (r.get("objects") or {}).values())
    outcomes = {}
    for item in queries:
        outcomes[item.get("outcome")] = outcomes.get(item.get("outcome"), 0) + 1
    embedding_tokens_estimate = sections * 250 + len(queries) * 30     # short synthetic sections and questions
    cost = {
        "generation": tokens_in / 1e6 * PRICES_USD["nova_micro_input_per_million"]
        + tokens_out / 1e6 * PRICES_USD["nova_micro_output_per_million"],
        "vector_queries": searches / 1e6 * PRICES_USD["vector_queries_per_million"],
        "embeddings": embedding_tokens_estimate / 1e6 * PRICES_USD["titan_embeddings_per_million_tokens"],
        "api_and_function_requests": len(queries) / 1e6 * (PRICES_USD["http_api_requests_per_million"]
                                                          + PRICES_USD["lambda_requests_per_million"]),
    }
    return {"deployment": deployment, "query_requests": len(queries), "outcomes": outcomes,
            "knowledge_base_searches": searches, "generation_calls": len(generated), "input_tokens": tokens_in,
            "output_tokens": tokens_out, "ingestion_runs": len(ingestions), "sections_ingested": sections,
            "estimated_usage_cost_usd": {k: round(v, 5) for k, v in cost.items()},
            "estimated_usage_cost_total_usd": round(sum(cost.values()), 4), "prices": PRICES_USD,
            "prices_date": PRICES_DATE,
            "not_included": "storage for hours, Lambda duration, DynamoDB requests, CloudWatch Logs, Cognito; see "
                            "COST_AND_CLEANUP.md for the full model"}
