"""Unified SSE streaming adapter for all LLM providers."""

from __future__ import annotations

import json
from typing import AsyncIterator

from fastapi.responses import StreamingResponse

from app.core.logging import get_logger
from app.security.error_sanitize import client_safe_llm_error

logger = get_logger(__name__)


async def sse_stream(
    token_iterator: AsyncIterator[str],
    *,
    on_complete: callable | None = None,
) -> AsyncIterator[str]:
    """Wrap an async token iterator into SSE (Server-Sent Events) format.

    Yields lines in the format: `data: {"token": "..."}\n\n`
    Ends with: `data: [DONE]\n\n`

    Args:
        token_iterator: Async iterator of text tokens from any LLM provider.
        on_complete: Optional async callback invoked with the full text after streaming completes.
            Not called when the stream fails (avoids persisting empty/error replies).
    """
    full_text = ""
    stream_failed = False
    try:
        async for token in token_iterator:
            full_text += token
            event = json.dumps({"token": token})
            yield f"data: {event}\n\n"
    except Exception as exc:
        stream_failed = True
        # Full diagnostics stay in logs; clients only get a safe message.
        logger.exception("sse_stream_error")
        error_event = json.dumps({"error": client_safe_llm_error(exc)})
        yield f"data: {error_event}\n\n"
    finally:
        yield "data: [DONE]\n\n"
        if on_complete and not stream_failed:
            try:
                await on_complete(full_text)
            except Exception:
                logger.exception("sse_on_complete_error")


def create_sse_response(token_iterator: AsyncIterator[str], **kwargs) -> StreamingResponse:
    """Create a FastAPI StreamingResponse with SSE headers."""
    return StreamingResponse(
        sse_stream(token_iterator, **kwargs),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
