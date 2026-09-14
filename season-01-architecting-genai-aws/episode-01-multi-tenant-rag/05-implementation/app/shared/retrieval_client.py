"""The retrieval call (CTL-007, CTL-016). It cannot build or change a constraint.

retrieve() accepts only a TenantScopedQuery issued by retrieval_scope.authorize_and_scope() and sends its filter
unchanged. The question is used only as retrievalQuery.text. No implicit filtering, query rewriting, reranking or
agent tools are used, and the number of results is fixed.

Results are reduced to an explicit field allow-list at this boundary (platform finding CH-09): the service also returns
x-amz-bedrock-kb-* metadata, scores and locations, and none of that travels further into the application.
"""
from dataclasses import dataclass

from shared.reason_codes import RETRIEVAL_SCOPE_INVALID, RETRIEVAL_UNAVAILABLE, Denied
from shared.retrieval_scope import TenantScopedQuery


@dataclass(frozen=True)
class RetrievedChunk:
    document_id: object      # str or None — the document_id attribute written at ingestion
    owner_attribute: object  # str or None — the owning_tenant attribute written at ingestion
    text: str


def retrieve(agent_runtime, knowledge_base_id, scoped):
    if not isinstance(scoped, TenantScopedQuery):
        raise Denied(RETRIEVAL_SCOPE_INVALID, "retrieve() requires a TenantScopedQuery")
    try:
        response = agent_runtime.retrieve(
            knowledgeBaseId=knowledge_base_id,
            retrievalQuery={"text": scoped.question},
            retrievalConfiguration={"vectorSearchConfiguration": {
                "numberOfResults": scoped.number_of_results,
                "filter": scoped.retrieval_filter,
            }},
        )
    except Exception as error:  # noqa: BLE001 — retrieval failure is never an empty, "clean" result
        raise Denied(RETRIEVAL_UNAVAILABLE, type(error).__name__) from error
    chunks = []
    for result in response.get("retrievalResults", []):
        metadata = result.get("metadata") or {}
        chunks.append(RetrievedChunk(
            document_id=metadata.get("document_id"),
            owner_attribute=metadata.get("owning_tenant"),
            text=(result.get("content") or {}).get("text", ""),
        ))
    return chunks
