"""Hybrid search retriever using Qdrant dense + sparse vectors."""

from __future__ import annotations

from app.core.config import get_settings
from app.core.logging import get_logger
from app.ingestion.embeddings import get_embedder
from app.vectorstore.collections import search_vectors

logger = get_logger(__name__)


async def retrieve(
    query: str,
    user_id: int,
    *,
    top_k: int | None = None,
    document_id: str | None = None,
    document_ids: list[str] | None = None,
) -> list[dict]:
    """Retrieve relevant chunks for a query using dense vector search.

    Args:
        query: The user's search query.
        user_id: Owner ID for multi-tenant filtering.
        top_k: Number of results to return (defaults to settings.RETRIEVAL_TOP_K).
        document_id: Optional filter to search within a specific document.
        document_ids: Optional allow-list of document IDs (current completed docs).

    Returns:
        List of result dicts with keys: chunk_id, score, text, document_id, page_number, chunk_index, metadata.
    """
    settings = get_settings()
    k = top_k or settings.RETRIEVAL_TOP_K

    embedder = get_embedder()
    query_vector = embedder.embed_query(query)

    results = search_vectors(
        dense_vector=query_vector,
        user_id=user_id,
        top_k=k,
        document_id=document_id,
        document_ids=document_ids,
    )

    logger.info(
        "retrieved_chunks",
        query_preview=query[:80],
        user_id=user_id,
        result_count=len(results),
    )
    return results
