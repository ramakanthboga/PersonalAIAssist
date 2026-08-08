"""Unit tests for chunking module."""

from __future__ import annotations

from app.rag.chunking import chunk_pages, Chunk


class TestChunking:
    def test_single_short_page(self):
        pages = [{"text": "Short text.", "page_number": 1, "metadata": {}}]
        chunks = chunk_pages(pages, "doc-1")
        assert len(chunks) == 1
        assert chunks[0].text == "Short text."
        assert chunks[0].document_id == "doc-1"
        assert chunks[0].page_number == 1

    def test_preserves_metadata(self):
        pages = [{"text": "Hello world.", "page_number": 1, "metadata": {"source_type": "pdf"}}]
        chunks = chunk_pages(pages, "doc-2")
        assert chunks[0].metadata.get("source_type") == "pdf"

    def test_multiple_pages(self):
        pages = [
            {"text": "Page one content.", "page_number": 1, "metadata": {}},
            {"text": "Page two content.", "page_number": 2, "metadata": {}},
        ]
        chunks = chunk_pages(pages, "doc-3")
        assert len(chunks) == 2
        assert chunks[0].page_number == 1
        assert chunks[1].page_number == 2

    def test_long_text_splits(self):
        long_text = "word " * 500
        pages = [{"text": long_text, "page_number": 1, "metadata": {}}]
        chunks = chunk_pages(pages, "doc-4", chunk_size=200, chunk_overlap=20)
        assert len(chunks) > 1
        for chunk in chunks:
            assert chunk.document_id == "doc-4"

    def test_chunk_index_increments(self):
        pages = [{"text": "a " * 500, "page_number": 1, "metadata": {}}]
        chunks = chunk_pages(pages, "doc-5", chunk_size=100, chunk_overlap=10)
        indices = [c.chunk_index for c in chunks]
        assert indices == list(range(len(chunks)))

    def test_empty_page_no_chunks(self):
        pages = [{"text": "", "page_number": 1, "metadata": {}}]
        chunks = chunk_pages(pages, "doc-6")
        assert len(chunks) == 0
