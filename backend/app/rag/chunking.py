"""Semantic chunking with metadata preservation."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class Chunk:
    """A text chunk with provenance metadata for RAG retrieval."""
    text: str
    document_id: str
    page_number: int
    chunk_index: int
    metadata: dict[str, str] = field(default_factory=dict)

    @property
    def token_estimate(self) -> int:
        """Rough token count (words * 1.3)."""
        return int(len(self.text.split()) * 1.3)


def chunk_pages(
    pages: list[dict],
    document_id: str,
    *,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
) -> list[Chunk]:
    """Split extracted pages into overlapping text chunks.

    Args:
        pages: List of dicts with keys: text, page_number, metadata.
        document_id: ID of the source document.
        chunk_size: Max characters per chunk (defaults to settings.CHUNK_SIZE).
        chunk_overlap: Character overlap between chunks (defaults to settings.CHUNK_OVERLAP).

    Returns:
        List of Chunk objects with metadata.
    """
    settings = get_settings()
    size = chunk_size or settings.CHUNK_SIZE
    overlap = chunk_overlap or settings.CHUNK_OVERLAP

    chunks: list[Chunk] = []
    chunk_index = 0

    for page in pages:
        text = page["text"]
        page_num = page["page_number"]
        page_meta = page.get("metadata", {})

        paragraphs = _split_into_paragraphs(text)

        current_chunk = ""
        for para in paragraphs:
            if current_chunk and len(current_chunk) + len(para) + 2 > size:
                chunks.append(Chunk(
                    text=current_chunk.strip(),
                    document_id=document_id,
                    page_number=page_num,
                    chunk_index=chunk_index,
                    metadata={**page_meta},
                ))
                chunk_index += 1
                if overlap > 0 and len(current_chunk) > overlap:
                    current_chunk = current_chunk[-overlap:]
                else:
                    current_chunk = ""

            current_chunk += ("\n\n" if current_chunk else "") + para

            while len(current_chunk) > size:
                split_point = _find_split_point(current_chunk, size)
                chunks.append(Chunk(
                    text=current_chunk[:split_point].strip(),
                    document_id=document_id,
                    page_number=page_num,
                    chunk_index=chunk_index,
                    metadata={**page_meta},
                ))
                chunk_index += 1
                current_chunk = current_chunk[split_point - overlap:] if overlap > 0 else current_chunk[split_point:]

        if current_chunk.strip():
            chunks.append(Chunk(
                text=current_chunk.strip(),
                document_id=document_id,
                page_number=page_num,
                chunk_index=chunk_index,
                metadata={**page_meta},
            ))
            chunk_index += 1

    logger.info("chunked_document", document_id=document_id, chunk_count=len(chunks))
    return chunks


def _split_into_paragraphs(text: str) -> list[str]:
    """Split text into paragraphs on double newlines, filtering empties."""
    raw = text.split("\n\n")
    return [p.strip() for p in raw if p.strip()]


def _find_split_point(text: str, max_len: int) -> int:
    """Find a clean split point (sentence end, then word boundary)."""
    for sep in (". ", ".\n", "? ", "! "):
        idx = text.rfind(sep, 0, max_len)
        if idx > max_len // 2:
            return idx + len(sep)
    idx = text.rfind(" ", 0, max_len)
    if idx > max_len // 2:
        return idx + 1
    return max_len
