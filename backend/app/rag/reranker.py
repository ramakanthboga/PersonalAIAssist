"""Reranker using Cohere Rerank or fallback score-based passthrough."""

from __future__ import annotations

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


async def rerank(
    query: str,
    results: list[dict],
    *,
    top_k: int | None = None,
) -> list[dict]:
    """Rerank retrieved results using Cohere Rerank, falling back to score-based ordering.

    Args:
        query: The original user query.
        results: List of result dicts (must contain 'text' key).
        top_k: Number of top results to return (defaults to settings.RERANKER_TOP_K).

    Returns:
        Reranked list of result dicts, trimmed to top_k.
    """
    settings = get_settings()
    k = top_k or settings.RERANKER_TOP_K

    if not results:
        return []

    if settings.COHERE_API_KEY:
        return await _cohere_rerank(query, results, k)

    logger.info("reranker_fallback", reason="no COHERE_API_KEY, using score-based ordering")
    return sorted(results, key=lambda r: r.get("score", 0), reverse=True)[:k]


async def _cohere_rerank(query: str, results: list[dict], top_k: int) -> list[dict]:
    """Rerank using Cohere Rerank API."""
    import cohere

    settings = get_settings()
    client = cohere.Client(api_key=settings.COHERE_API_KEY)

    documents = [r["text"] for r in results]

    try:
        response = client.rerank(
            query=query,
            documents=documents,
            model=settings.RERANKER_MODEL,
            top_n=top_k,
        )
    except Exception:
        logger.exception("cohere_rerank_failed")
        return sorted(results, key=lambda r: r.get("score", 0), reverse=True)[:top_k]

    reranked: list[dict] = []
    for item in response.results:
        result = results[item.index].copy()
        result["rerank_score"] = item.relevance_score
        reranked.append(result)

    logger.info("reranked_results", original_count=len(results), reranked_count=len(reranked))
    return reranked
