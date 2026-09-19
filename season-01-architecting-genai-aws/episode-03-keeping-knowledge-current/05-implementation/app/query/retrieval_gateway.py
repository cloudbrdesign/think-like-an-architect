"""Retrieval gateway: the ONLY code that calls the knowledge bases (CTL-005, CTL-011, CTL-012, CTL-013; boundary B4).

It accepts only TierQuery objects produced by core/constraints.py and sends each one's constraint unchanged. It cannot
build, widen or drop a constraint, and there is no other search path in this function. The question is used only as
the retrieval query text. Results are reduced to identifiers, attributes, score and text at this boundary.

An empty result means "nothing eligible matched" (SPK-E02-A C8), never "no restriction". A service error is a refusal,
never an empty result.
"""
from core.constraints import TierQuery
from core.reason_codes import REFUSED_CONSTRAINT_INCOMPLETE, RETRIEVAL_ERROR, Refusal
from core.verification import RetrievedChunk

RESULTS_PER_TIER = 5
CHUNK_ID_KEY = "x-amz-bedrock-kb-chunk-id"


def retrieve(agent_runtime, knowledge_base_ids, question, tier_queries, tiers_called):
    """Search each tier with its constraint. Appends each tier to `tiers_called` BEFORE calling it (audit evidence)."""
    chunks = []
    for query in tier_queries:
        if not isinstance(query, TierQuery) or not query.retrieval_filter or query.tier not in knowledge_base_ids:
            raise Refusal(REFUSED_CONSTRAINT_INCOMPLETE, "not a complete tier query")
        tiers_called.append(query.tier)
        try:
            response = agent_runtime.retrieve(
                knowledgeBaseId=knowledge_base_ids[query.tier],
                retrievalQuery={"text": question},
                retrievalConfiguration={"vectorSearchConfiguration": {
                    "numberOfResults": RESULTS_PER_TIER, "filter": query.retrieval_filter}})
        except Exception as error:  # noqa: BLE001
            raise Refusal(RETRIEVAL_ERROR, type(error).__name__) from error
        for position, result in enumerate(response.get("retrievalResults", [])):
            metadata = result.get("metadata") or {}
            chunks.append(RetrievedChunk(
                chunk_id=str(metadata.get(CHUNK_ID_KEY) or f"{query.tier}-unidentified-{position}"),
                tier=query.tier,
                document_id=metadata.get("document_id"), section_id=metadata.get("section_id"),
                label=metadata.get("label"), scope=metadata.get("scope"),
                record_version=metadata.get("record_version"),
                score=float(result.get("score") or 0.0),
                text=(result.get("content") or {}).get("text", "")))
    return sorted(chunks, key=lambda c: (-c.score, c.chunk_id))
