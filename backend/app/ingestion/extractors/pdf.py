"""PDF text extraction using PyMuPDF (fast path) + PyMuPDF4LLM (fallback)."""

from __future__ import annotations

import pymupdf
import pymupdf4llm

from app.ingestion.extractors import ExtractedPage

# Pages with at least this many chars of native text are treated as digital text.
_MIN_NATIVE_CHARS = 40


def extract_pdf(file_path: str) -> list[ExtractedPage]:
    """Extract text from a PDF, one ExtractedPage per page.

    Uses fast native PyMuPDF text extraction when the PDF has a real text
    layer. Falls back to a single-pass PyMuPDF4LLM markdown extraction
    (with layout/OCR) for scanned or image-heavy PDFs.
    """
    doc = pymupdf.open(file_path)
    total_pages = len(doc)
    try:
        native_pages = _extract_native_text(doc, total_pages)
        # Prefer native when most non-empty pages have usable text.
        if native_pages and len(native_pages) >= max(1, (total_pages + 1) // 2):
            return native_pages
    finally:
        doc.close()

    return _extract_markdown_pages(file_path, total_pages)


def _extract_native_text(doc: pymupdf.Document, total_pages: int) -> list[ExtractedPage]:
    """Cheap digital-text extraction — one get_text() call per page."""
    pages: list[ExtractedPage] = []
    for page_num in range(total_pages):
        text = doc[page_num].get_text("text").strip()
        if len(text) < _MIN_NATIVE_CHARS:
            continue
        pages.append(
            ExtractedPage(
                text=text,
                page_number=page_num + 1,
                metadata={"source_type": "pdf", "total_pages": str(total_pages), "extractor": "pymupdf"},
            )
        )
    return pages


def _extract_markdown_pages(file_path: str, total_pages: int | None = None) -> list[ExtractedPage]:
    """Single-pass markdown extraction for layout-heavy / scanned PDFs."""
    chunks = pymupdf4llm.to_markdown(file_path, page_chunks=True)
    if not isinstance(chunks, list):
        text = str(chunks).strip()
        if not text:
            return []
        return [
            ExtractedPage(
                text=text,
                page_number=1,
                metadata={"source_type": "pdf", "total_pages": "1", "extractor": "pymupdf4llm"},
            )
        ]

    if total_pages is None:
        total_pages = len(chunks)

    pages: list[ExtractedPage] = []
    for idx, chunk in enumerate(chunks):
        if isinstance(chunk, dict):
            text = (chunk.get("text") or "").strip()
            meta = chunk.get("metadata") or {}
            raw_page = meta.get("page", meta.get("page_number"))
            if raw_page is None:
                page_number = idx + 1
            else:
                try:
                    n = int(raw_page)
                except (TypeError, ValueError):
                    n = idx
                # Normalize 0-based metadata to 1-based page numbers.
                page_number = n + 1 if n == idx else max(1, n if n > 0 else n + 1)
        else:
            text = str(chunk).strip()
            page_number = idx + 1

        if not text:
            continue
        pages.append(
            ExtractedPage(
                text=text,
                page_number=page_number,
                metadata={
                    "source_type": "pdf",
                    "total_pages": str(total_pages),
                    "extractor": "pymupdf4llm",
                },
            )
        )
    return pages
