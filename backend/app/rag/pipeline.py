"""Main RAG pipeline orchestrator – ties retrieval, reranking, and prompt building together."""

from __future__ import annotations

import re
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.database.repositories.document_repo import DocumentRepository
from app.rag.prompt_builder import RAGPrompt, build_help_prompt, build_no_documents_prompt, build_prompt
from app.rag.query_classifier import QueryType, classify_query
from app.rag.reranker import rerank
from app.rag.retriever import retrieve
from app.rag.suggested_prompts import format_suggested_prompts_markdown
from app.vectorstore.collections import list_document_chunks

logger = get_logger(__name__)


@dataclass
class RAGResult:
    """Complete result from the RAG pipeline."""
    prompt: RAGPrompt
    query_type: QueryType
    retrieved_count: int
    reranked_count: int
    has_documents: bool = True
    # When False, chat must refuse without calling the LLM (no / weak context).
    should_call_llm: bool = True
    # Optional canned answer for help / meta flows (no LLM).
    canned_answer: str | None = None


def _chunk_relevance_score(chunk: dict) -> float:
    if "rerank_score" in chunk:
        return float(chunk.get("rerank_score") or 0.0)
    return float(chunk.get("score") or 0.0)


def _filter_by_min_score(chunks: list[dict], settings, *, relaxed: bool = False) -> list[dict]:
    """Keep only chunks that meet the minimum relevance threshold."""
    if not chunks:
        return []

    use_rerank = any("rerank_score" in c for c in chunks)
    min_score = settings.MIN_RERANK_SCORE if use_rerank else settings.MIN_RETRIEVAL_SCORE
    if relaxed:
        min_score = min_score * 0.5

    kept = [c for c in chunks if _chunk_relevance_score(c) >= min_score]
    if len(kept) < len(chunks):
        logger.info(
            "rag_dropped_low_score_chunks",
            dropped=len(chunks) - len(kept),
            kept=len(kept),
            min_score=min_score,
            use_rerank=use_rerank,
            relaxed=relaxed,
        )
    return kept


def _merge_chunks(*groups: list[dict]) -> list[dict]:
    """Merge chunk lists by chunk_id, keeping the highest score."""
    by_id: dict[str, dict] = {}
    for group in groups:
        for chunk in group:
            cid = str(chunk.get("chunk_id") or "")
            if not cid:
                continue
            prev = by_id.get(cid)
            if prev is None or _chunk_relevance_score(chunk) > _chunk_relevance_score(prev):
                by_id[cid] = chunk
    return list(by_id.values())


def _sort_chunks_for_summary(chunks: list[dict]) -> list[dict]:
    return sorted(
        chunks,
        key=lambda c: (
            str(c.get("document_id", "")),
            int(c.get("page_number") or 0),
            int(c.get("chunk_index") or 0),
        ),
    )


async def run_rag_pipeline(
    query: str,
    user_id: int,
    db: AsyncSession,
    *,
    document_id: str | None = None,
    document_ids: list[str] | None = None,
) -> RAGResult:
    """Execute the full RAG pipeline: classify -> retrieve -> rerank -> build prompt.

    When the user has no completed documents, skips embedding/retrieval entirely
    (avoids slow model load for chats like "Hi").

    Answers are grounded only in currently completed documents. Empty or weak
    retrieval sets ``should_call_llm=False`` so chat refuses without general knowledge.

    Scope:
      - ``document_ids`` / ``document_id``: search only those completed docs (owned).
      - neither: search all of the user's completed documents.
    """
    settings = get_settings()
    repo = DocumentRepository(db)

    # Normalize single + multi selection into one allow-list
    selected_ids: list[str] = []
    if document_ids:
        for did in document_ids:
            if did and did not in selected_ids:
                selected_ids.append(did)
    if document_id and document_id not in selected_ids:
        selected_ids.append(document_id)

    if not selected_ids:
        completed_ids = await repo.list_completed_ids_by_user(user_id)
        if not completed_ids:
            query_type = classify_query(query)
            logger.info(
                "rag_pipeline_skip_no_documents",
                query_type=query_type.value,
                query=query[:80],
            )
            return RAGResult(
                prompt=build_no_documents_prompt(query),
                query_type=query_type,
                retrieved_count=0,
                reranked_count=0,
                has_documents=False,
                should_call_llm=False,
            )
    else:
        completed_ids = []
        for did in selected_ids:
            doc = await repo.get_by_id(did, user_id)
            if doc is not None and doc.status == "completed":
                completed_ids.append(did)
        if not completed_ids:
            query_type = classify_query(query)
            return RAGResult(
                prompt=build_no_documents_prompt(query),
                query_type=query_type,
                retrieved_count=0,
                reranked_count=0,
                has_documents=False,
                should_call_llm=False,
            )

    # Resolve filenames for help / listing responses
    completed_docs = []
    for did in completed_ids:
        doc = await repo.get_by_id(did, user_id)
        if doc and doc.status == "completed":
            completed_docs.append(doc)
    doc_names = {d.id: d.original_filename for d in completed_docs}
    filenames = [d.original_filename for d in completed_docs]

    # Step 1: Classify the query
    query_type = classify_query(query)
    logger.info(
        "rag_pipeline_start",
        query_type=query_type.value,
        query=query[:80],
        scoped_docs=len(completed_ids),
        explicit_scope=bool(selected_ids),
    )

    # HELP with documents: retrieve + LLM so suggestions match file content / goal.
    # (Canned templates are only a fallback when retrieval finds nothing.)

    # Inventory listing of uploaded docs (no vector search needed)
    if query_type == QueryType.LISTING and re_wants_document_inventory(query):
        lines = ["Here are your currently uploaded documents:\n"]
        for i, name in enumerate(filenames, 1):
            lines.append(f"{i}. **{name}**")
        lines.append(
            "\nAsk me to summarize one, list its key points, or explain a section "
            "with examples from the document."
        )
        answer = "\n".join(lines)
        return RAGResult(
            prompt=build_help_prompt(query, answer),
            query_type=query_type,
            retrieved_count=0,
            reranked_count=0,
            has_documents=True,
            should_call_llm=False,
            canned_answer=answer,
        )

    # Step 2: Retrieve relevant chunks (allow-list: only current completed docs)
    retrieval_k = settings.RETRIEVAL_TOP_K
    rerank_k = settings.RERANKER_TOP_K
    if query_type == QueryType.COMPARISON:
        retrieval_k = min(retrieval_k * 2, 30)
    if query_type == QueryType.SYNTHESIS:
        retrieval_k = settings.SYNTHESIS_RETRIEVAL_TOP_K
        rerank_k = settings.SYNTHESIS_CONTEXT_CHUNKS
    if query_type == QueryType.HELP:
        # Broad context so prompt suggestions reflect real document topics
        retrieval_k = max(retrieval_k, min(settings.SYNTHESIS_RETRIEVAL_TOP_K, 20))
        rerank_k = max(rerank_k, min(settings.SYNTHESIS_CONTEXT_CHUNKS, 12))

    results = await retrieve(
        query,
        user_id,
        top_k=retrieval_k,
        document_id=None,
        document_ids=completed_ids,
    )

    # Step 3: Rerank (for synthesis keep a large context window)
    reranked = await rerank(query, results, top_k=rerank_k)

    # Step 3b: For summaries / help, also pull page-spread coverage from the docs
    coverage_chunks: list[dict] = []
    if query_type in (QueryType.SYNTHESIS, QueryType.HELP):
        coverage_chunks = list_document_chunks(
            user_id,
            completed_ids,
            limit=settings.SYNTHESIS_CONTEXT_CHUNKS,
        )

    # Step 4: Keep only live completed documents
    candidate = _merge_chunks(reranked, coverage_chunks)
    live_chunks = [r for r in candidate if r.get("document_id") in doc_names]
    if len(live_chunks) < len(candidate):
        logger.warning(
            "rag_dropped_orphan_chunks",
            dropped=len(candidate) - len(live_chunks),
            kept=len(live_chunks),
            user_id=user_id,
        )

    # Step 5: Score filter — synthesis/help keep broad page coverage
    coverage_ids = {str(c.get("chunk_id")) for c in coverage_chunks}
    if query_type in (QueryType.SYNTHESIS, QueryType.HELP):
        semantic = _filter_by_min_score(
            [c for c in live_chunks if str(c.get("chunk_id")) not in coverage_ids],
            settings,
            relaxed=True,
        )
        coverage_live = [c for c in live_chunks if str(c.get("chunk_id")) in coverage_ids]
        relevant_chunks = _sort_chunks_for_summary(
            _merge_chunks(semantic, coverage_live)
        )[: settings.SYNTHESIS_CONTEXT_CHUNKS]
    else:
        relevant_chunks = _filter_by_min_score(live_chunks, settings)

    # Step 6: Build the prompt
    prompt = build_prompt(
        query=query,
        retrieved_chunks=relevant_chunks,
        query_type=query_type,
        document_names=doc_names,
    )

    should_call_llm = len(relevant_chunks) > 0
    canned_answer: str | None = None

    # HELP with no usable chunks: fall back to filename-based templates
    if query_type == QueryType.HELP and not should_call_llm:
        canned_answer = format_suggested_prompts_markdown(filenames, user_query=query)
        return RAGResult(
            prompt=build_help_prompt(query, canned_answer),
            query_type=query_type,
            retrieved_count=len(results),
            reranked_count=0,
            has_documents=True,
            should_call_llm=False,
            canned_answer=canned_answer,
        )

    logger.info(
        "rag_pipeline_complete",
        query_type=query_type.value,
        retrieved=len(results),
        coverage=len(coverage_chunks),
        relevant=len(relevant_chunks),
        citations=len(prompt.citations),
        should_call_llm=should_call_llm,
    )

    return RAGResult(
        prompt=prompt,
        query_type=query_type,
        retrieved_count=len(results),
        reranked_count=len(relevant_chunks),
        has_documents=True,
        should_call_llm=should_call_llm,
    )


def re_wants_document_inventory(query: str) -> bool:
    """True when the user is asking which files are uploaded, not content inside them."""
    q = query.lower()
    return bool(
        re.search(
            r"\b(?:list|show|what|which|how many)\b.*\bdocuments?\b",
            q,
        )
    )
