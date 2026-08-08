"""Zero-shot prompt builder with citation tracking for RAG responses."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.core.logging import get_logger
from app.rag.query_classifier import QueryType

logger = get_logger(__name__)


@dataclass
class Citation:
    """A source citation for an answer."""
    document_id: str
    document_name: str
    page_number: int
    chunk_text: str
    relevance_score: float = 0.0


@dataclass
class RAGPrompt:
    """A constructed prompt with tracked citations."""
    system_message: str
    user_message: str
    citations: list[Citation] = field(default_factory=list)


_SYSTEM_BASE = (
    "You are a personal AI assistant that answers questions based ONLY on the user's "
    "uploaded documents. Follow these rules strictly:\n\n"
    "1. ONLY use information from the provided context below. The context is the sole "
    "source of truth.\n"
    "2. If the answer is not in the context, say exactly: "
    '"I couldn\'t find that information in your uploaded documents." '
    "Do not add extra facts afterward.\n"
    "3. Citations: when a claim comes from context, add a compact marker like [1] or "
    "[2] matching the Source number in the context block. Place markers at the end of "
    "the relevant sentence or bullet — never more than once per claim.\n"
    "4. Do NOT write filenames, PDF titles, or page numbers in the answer body. "
    "Never write phrases like \"(Source: …pdf, Page N)\", \"(Page N)\", or "
    "\"according to document X page Y\". The UI already shows full source details "
    "separately.\n"
    "5. If multiple documents contain conflicting information, present both values "
    "and note the discrepancy.\n"
    "6. Never fabricate, guess, use general knowledge, or answer from training data.\n"
    "7. Do not explore codebases, browse the web, or use external tools.\n"
    "8. Format responses in clear, readable markdown: short paragraphs, real headings "
    "when useful, and markdown tables (not ASCII/plain-text tables) for step-by-step "
    "or comparisons.\n"
)

_SYSTEM_NO_DOCS = (
    "You are PersonalAIAssist. The user has not uploaded any documents yet. "
    "Do NOT answer general-knowledge questions. Do NOT invent document contents. "
    "Tell them to upload files from the Docs page first, then ask about those files. "
    "Do not explore or modify any codebase. This is a chat reply only."
)

_QUERY_TYPE_INSTRUCTIONS = {
    QueryType.LOOKUP: (
        "The user is looking for a specific fact. Provide a concise, direct answer "
        "with the exact value from the document context only."
    ),
    QueryType.SYNTHESIS: (
        "The user wants a summary or explanation of the document(s). "
        "Use ALL provided context pages/chunks — do not summarize only one page. "
        "Produce a thorough structured overview. If they ask for a specific length "
        "(e.g. 100 lines), aim for that depth using the available context; "
        "if context is incomplete, summarize everything you have thoroughly "
        "and note which parts of the document were covered, without refusing."
    ),
    QueryType.COMPARISON: (
        "The user wants to compare information across documents. Present a clear "
        "side-by-side comparison using only the provided context."
    ),
    QueryType.LISTING: (
        "The user wants a list of items from the documents. Present the results as a "
        "well-organized list from the provided context only. Include brief examples "
        "when the context contains them."
    ),
    QueryType.HELP: (
        "The user wants suggested questions/prompts they can ask about the provided "
        "document context (and their stated learning goal if any).\n"
        "Rules for this reply:\n"
        "- Ground every suggestion in topics, risks, controls, or sections that "
        "actually appear in the context — do not invent unrelated topics.\n"
        "- Return 6–8 ready-to-copy prompts the user can paste next. Number them.\n"
        "- Tailor prompts to their goal when stated (e.g. learning, exam prep, "
        "implementation). Prefer 'explain X with examples from the document', "
        "'list …', 'compare …', 'what does the doc say about …'.\n"
        "- Do NOT answer those prompts yourself. Do NOT write a lecture or essay.\n"
        "- Keep filenames out of every line; mention the document once in a short intro.\n"
        "- Compact [n] citations are optional; prefer clean numbered prompts."
    ),
    QueryType.GENERAL: (
        "Answer the user's question using ONLY the provided context. "
        "If context is insufficient, refuse."
    ),
}


def build_prompt(
    query: str,
    retrieved_chunks: list[dict],
    query_type: QueryType,
    *,
    document_names: dict[str, str] | None = None,
) -> RAGPrompt:
    """Build a zero-shot RAG prompt with context and citations.

    Args:
        query: The user's question.
        retrieved_chunks: Chunks from the retriever/reranker, each with
            text, document_id, page_number, chunk_index, score/rerank_score.
        query_type: Classified query type for instruction tuning.
        document_names: Optional mapping of document_id -> original_filename.

    Returns:
        RAGPrompt with system message, user message, and citations list.
    """
    doc_names = document_names or {}
    type_instruction = _QUERY_TYPE_INSTRUCTIONS.get(query_type, _QUERY_TYPE_INSTRUCTIONS[QueryType.GENERAL])

    system_message = f"{_SYSTEM_BASE}\n{type_instruction}"

    context_parts: list[str] = []
    citations: list[Citation] = []

    for i, chunk in enumerate(retrieved_chunks):
        doc_id = chunk.get("document_id", "unknown")
        doc_name = doc_names.get(doc_id, doc_id)
        page_num = chunk.get("page_number", 0)
        text = chunk.get("text", "")
        score = chunk.get("rerank_score", chunk.get("score", 0.0))

        # Numbered labels so the model can cite with compact [1], [2], … markers.
        ref_label = f"[Source {i + 1}] ({doc_name}, page {page_num})"
        context_parts.append(f"{ref_label}\n{text}")

        citations.append(Citation(
            document_id=doc_id,
            document_name=doc_name,
            page_number=page_num,
            chunk_text=text[:200],
            relevance_score=score,
        ))

    context_block = "\n\n---\n\n".join(context_parts) if context_parts else "(No relevant documents found.)"

    user_message = f"## Context from your documents:\n\n{context_block}\n\n## Question:\n{query}"

    logger.info(
        "built_prompt",
        query_type=query_type.value,
        context_chunks=len(retrieved_chunks),
        citation_count=len(citations),
    )

    return RAGPrompt(
        system_message=system_message,
        user_message=user_message,
        citations=citations,
    )


def build_no_documents_prompt(query: str) -> RAGPrompt:
    """Prompt for when the user has no indexed documents (LLM usually skipped)."""
    return RAGPrompt(
        system_message=_SYSTEM_NO_DOCS,
        user_message=query,
        citations=[],
    )


def build_help_prompt(query: str, answer: str) -> RAGPrompt:
    """Prompt shell for canned help / inventory replies (LLM usually skipped)."""
    return RAGPrompt(
        system_message=_QUERY_TYPE_INSTRUCTIONS[QueryType.HELP],
        user_message=f"{query}\n\n{answer}",
        citations=[],
    )
