"""Chat routes – send messages, list conversations, get history."""

from __future__ import annotations

import json
import re

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_rate_limited_user
from app.core.config import LLMProviderName, get_settings
from app.core.exceptions import AppError
from app.core.logging import get_logger
from app.database.models import User
from app.database.session import get_db
from app.llm.base import LLMResponse
from app.llm.factory import get_chat_llm_provider
from app.llm.streaming import create_sse_response
from app.rag.pipeline import run_rag_pipeline
from app.security.error_sanitize import (
    client_safe_llm_error,
    client_safe_rag_error,
    public_detail_from_exc,
)
from app.services.chat_service import ChatService

logger = get_logger(__name__)
router = APIRouter(prefix="/chat")

_GREETING_RE = re.compile(
    r"^\s*(hi|hello|hey|hiya|howdy|good\s+(morning|afternoon|evening))"
    r"([\s,!.?-]+.*)?$",
    re.IGNORECASE,
)

_NO_DOCS_GREETING = (
    "Hello! I'm **PersonalAIAssist**.\n\n"
    "You don't have any documents uploaded yet. "
    "Go to **Docs**, upload a PDF or file, wait until it shows as completed, "
    "then ask me questions about it."
)

_WITH_DOCS_GREETING = (
    "Hello! I'm **PersonalAIAssist**.\n\n"
    "I answer questions based on your uploaded documents. Try prompts like:\n"
    "1. Summarize the document\n"
    "2. List the top risks / key points with examples from the document\n"
    "3. Explain the first major section in simple terms\n\n"
    "You can also ask: **suggest prompts** — I'll tailor examples to your files."
)

_NO_DOCS_ANSWER = (
    "I don't have any of your documents indexed yet, so I can't look that up "
    "in your files.\n\n"
    "Please upload documents from the **Docs** page first, then ask again."
)

_NOT_IN_DOCS_ANSWER = (
    "I couldn't find that information in your uploaded documents.\n\n"
    "I only answer based on files currently listed under **Docs**. "
    "Try asking **suggest prompts** for examples, or rephrase using words "
    "that appear in the document (titles, section names, risk IDs)."
)


async def _iter_text(text: str):
    """Yield a short reply as streamed tokens (no LLM call)."""
    step = 40
    for i in range(0, len(text), step):
        yield text[i : i + step]


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=10000)
    conversation_id: str | None = None
    document_id: str | None = None
    document_ids: list[str] | None = Field(default=None, max_length=100)
    stream: bool = True
    provider: LLMProviderName | None = None
    model: str | None = None


class CitationOut(BaseModel):
    document: str
    page: int
    chunk: str


class ChatResponse(BaseModel):
    answer: str
    conversation_id: str
    citations: list[CitationOut]
    confidence: float
    model: str
    usage: dict[str, int]


class ConversationOut(BaseModel):
    id: str
    title: str | None
    created_at: str
    updated_at: str


class MessageOut(BaseModel):
    id: str
    role: str
    content: str
    citations: str | None
    created_at: str


@router.post("/")
async def send_message(
    body: ChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_rate_limited_user),
):
    chat_svc = ChatService(db)

    # Get or create conversation
    if body.conversation_id:
        try:
            await chat_svc.get_conversation(body.conversation_id, current_user.id)
        except AppError:
            raise HTTPException(status_code=404, detail="Conversation not found")
        conversation_id = body.conversation_id
    else:
        conv = await chat_svc.create_conversation(
            current_user.id,
            title=body.message[:100],
        )
        conversation_id = conv.id

    # Save user message
    await chat_svc.add_message(conversation_id, current_user.id, "user", body.message)

    # Commit immediately so SQLite does not stay locked during RAG + LLM (can take minutes).
    await db.commit()

    # Run RAG pipeline
    try:
        rag_result = await run_rag_pipeline(
            query=body.message,
            user_id=current_user.id,
            db=db,
            document_id=body.document_id,
            document_ids=body.document_ids,
        )
    except Exception as exc:
        logger.exception("rag_pipeline_error")
        raise HTTPException(status_code=500, detail=client_safe_rag_error(exc))

    citations = [
        CitationOut(
            document=c.document_name,
            page=c.page_number,
            chunk=c.chunk_text,
        )
        for c in rag_result.prompt.citations
    ]
    citation_json = json.dumps([c.model_dump() for c in citations])
    user_id = current_user.id
    is_greeting = bool(_GREETING_RE.match(body.message.strip()))

    # Fast path: no documents, help prompts, or no sufficiently relevant chunks
    if not rag_result.should_call_llm:
        if rag_result.canned_answer:
            answer = rag_result.canned_answer
        elif is_greeting:
            answer = _WITH_DOCS_GREETING if rag_result.has_documents else _NO_DOCS_GREETING
        elif not rag_result.has_documents:
            answer = _NO_DOCS_ANSWER
        else:
            answer = _NOT_IN_DOCS_ANSWER

        logger.info(
            "chat_fast_path_abstain",
            conversation_id=conversation_id,
            has_documents=rag_result.has_documents,
            is_greeting=is_greeting,
            query_type=rag_result.query_type.value,
            canned=bool(rag_result.canned_answer),
        )

        if body.stream:
            async def on_stream_complete(full_text: str):
                from app.database.session import async_session_factory

                async with async_session_factory() as session:
                    svc = ChatService(session)
                    await svc.add_message(
                        conversation_id, user_id, "assistant", full_text, citations="[]"
                    )
                    await session.commit()

            return create_sse_response(_iter_text(answer), on_complete=on_stream_complete)

        await chat_svc.add_message(
            conversation_id, current_user.id, "assistant", answer, citations="[]"
        )
        return ChatResponse(
            answer=answer,
            conversation_id=conversation_id,
            citations=[],
            confidence=0.0,
            model="local-fast-path",
            usage={},
        )

    # Build LLM messages
    messages = [
        {"role": "system", "content": rag_result.prompt.system_message},
        {"role": "user", "content": rag_result.prompt.user_message},
    ]

    # Get LLM provider (Cursor auto-falls back in Docker)
    try:
        provider = get_chat_llm_provider(body.provider)
    except (AppError, ValueError) as exc:
        raise HTTPException(
            status_code=400,
            detail=public_detail_from_exc(exc, fallback="Invalid chat configuration."),
        )

    settings = get_settings()
    max_tokens = settings.LLM_MAX_TOKENS
    # Summaries need more room (e.g. "summarize in 100 lines").
    if rag_result.query_type.value == "synthesis":
        max_tokens = max(max_tokens, 4096)

    # Streaming response
    if body.stream:
        async def on_stream_complete(full_text: str):
            # Fresh session – request DB session must not be held across the LLM call.
            from app.database.session import async_session_factory

            async with async_session_factory() as session:
                svc = ChatService(session)
                await svc.add_message(
                    conversation_id, user_id, "assistant", full_text, citations=citation_json
                )
                await session.commit()

        token_stream = provider.stream(
            messages,
            model=body.model,
            temperature=settings.LLM_TEMPERATURE,
            max_tokens=max_tokens,
        )
        return create_sse_response(token_stream, on_complete=on_stream_complete)

    # Non-streaming response
    try:
        llm_response: LLMResponse = await provider.generate(
            messages,
            model=body.model,
            temperature=settings.LLM_TEMPERATURE,
            max_tokens=max_tokens,
        )
    except AppError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail=client_safe_llm_error(exc.message),
        )

    # Save assistant message
    await chat_svc.add_message(
        conversation_id, current_user.id, "assistant", llm_response.content, citations=citation_json
    )

    # Calculate confidence from reranker scores
    scores = [c.relevance_score for c in rag_result.prompt.citations if c.relevance_score > 0]
    confidence = sum(scores) / len(scores) if scores else 0.0

    return ChatResponse(
        answer=llm_response.content,
        conversation_id=conversation_id,
        citations=citations,
        confidence=round(min(confidence, 1.0), 2),
        model=llm_response.model,
        usage=llm_response.usage,
    )


@router.get("/conversations", response_model=list[ConversationOut])
async def list_conversations(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_rate_limited_user),
):
    chat_svc = ChatService(db)
    conversations = await chat_svc.list_conversations(current_user.id, limit=limit, offset=offset)
    return [
        ConversationOut(
            id=c.id,
            title=c.title,
            created_at=c.created_at.isoformat(),
            updated_at=c.updated_at.isoformat(),
        )
        for c in conversations
    ]


@router.get("/conversations/{conversation_id}", response_model=list[MessageOut])
async def get_conversation_messages(
    conversation_id: str,
    limit: int = Query(default=100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_rate_limited_user),
):
    chat_svc = ChatService(db)
    try:
        messages = await chat_svc.get_messages(conversation_id, current_user.id, limit=limit)
    except AppError:
        raise HTTPException(status_code=404, detail="Conversation not found")

    return [
        MessageOut(
            id=m.id,
            role=m.role,
            content=m.content,
            citations=m.citations,
            created_at=m.created_at.isoformat(),
        )
        for m in messages
    ]


@router.delete("/conversations/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    conversation_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_rate_limited_user),
):
    chat_svc = ChatService(db)
    try:
        await chat_svc.delete_conversation(conversation_id, current_user.id)
    except AppError:
        raise HTTPException(status_code=404, detail="Conversation not found")


@router.get("/providers")
async def list_providers(current_user: User = Depends(get_rate_limited_user)):
    """Return the active LLM provider only — do not reveal which API keys exist."""
    settings = get_settings()
    _ = current_user
    return {
        "active": settings.LLM_PROVIDER.value,
        "model": settings.LLM_MODEL,
    }
