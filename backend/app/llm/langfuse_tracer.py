"""Langfuse tracing integration for LLM calls."""

from __future__ import annotations

from typing import Any

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_langfuse = None


def get_langfuse():
    """Return the singleton Langfuse client, or None if not configured."""
    global _langfuse
    settings = get_settings()

    if _langfuse is not None:
        return _langfuse

    if not settings.LANGFUSE_PUBLIC_KEY or not settings.LANGFUSE_SECRET_KEY:
        logger.debug("langfuse_disabled", reason="keys not configured")
        return None

    try:
        from langfuse import Langfuse

        _langfuse = Langfuse(
            public_key=settings.LANGFUSE_PUBLIC_KEY,
            secret_key=settings.LANGFUSE_SECRET_KEY,
            host=settings.LANGFUSE_HOST,
        )
        logger.info("langfuse_initialized", host=settings.LANGFUSE_HOST)
        return _langfuse
    except ImportError:
        logger.warning("langfuse_not_installed")
        return None
    except Exception:
        logger.exception("langfuse_init_failed")
        return None


def trace_llm_call(
    *,
    name: str,
    user_id: str,
    input_messages: list[dict[str, str]],
    output: str,
    model: str,
    usage: dict[str, int],
    metadata: dict[str, Any] | None = None,
) -> None:
    """Record an LLM call in Langfuse for observability."""
    lf = get_langfuse()
    if lf is None:
        return

    try:
        trace = lf.trace(
            name=name,
            user_id=user_id,
            metadata=metadata or {},
        )
        trace.generation(
            name=f"{name}_generation",
            model=model,
            input=input_messages,
            output=output,
            usage={
                "input": usage.get("prompt_tokens", 0),
                "output": usage.get("completion_tokens", 0),
                "total": usage.get("total_tokens", 0),
            },
            metadata=metadata or {},
        )
    except Exception:
        logger.exception("langfuse_trace_failed")


def trace_rag_retrieval(
    *,
    user_id: str,
    query: str,
    query_type: str,
    retrieved_count: int,
    reranked_count: int,
    document_ids: list[str],
) -> None:
    """Record a RAG retrieval step in Langfuse."""
    lf = get_langfuse()
    if lf is None:
        return

    try:
        trace = lf.trace(
            name="rag_retrieval",
            user_id=user_id,
            metadata={
                "query_type": query_type,
                "retrieved_count": retrieved_count,
                "reranked_count": reranked_count,
            },
        )
        trace.span(
            name="retrieval",
            input={"query": query},
            output={"document_ids": document_ids, "count": retrieved_count},
        )
    except Exception:
        logger.exception("langfuse_rag_trace_failed")


def flush_langfuse() -> None:
    """Flush any pending Langfuse events."""
    lf = get_langfuse()
    if lf is not None:
        try:
            lf.flush()
        except Exception:
            logger.exception("langfuse_flush_failed")
