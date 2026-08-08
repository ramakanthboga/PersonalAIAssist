"""Plain text and Markdown extraction."""

from __future__ import annotations

from pathlib import Path

from app.ingestion.extractors import ExtractedPage


def extract_text(file_path: str) -> list[ExtractedPage]:
    """Extract text from plain text or markdown files."""
    content = Path(file_path).read_text(encoding="utf-8", errors="replace")
    if not content.strip():
        return []

    ext = Path(file_path).suffix.lower()
    return [ExtractedPage(
        text=content,
        page_number=1,
        metadata={"source_type": "markdown" if ext == ".md" else "text"},
    )]
