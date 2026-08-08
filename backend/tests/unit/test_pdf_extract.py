"""Unit tests for PDF extraction performance path."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.ingestion.extractors.pdf import extract_pdf


class TestPdfExtract:
    def test_uses_native_text_when_pages_have_content(self):
        page = MagicMock()
        page.get_text.return_value = "Enough native text content for this page to count."

        doc = MagicMock()
        doc.__len__.return_value = 2
        doc.__getitem__.side_effect = lambda i: page

        with patch("app.ingestion.extractors.pdf.pymupdf.open", return_value=doc):
            with patch("app.ingestion.extractors.pdf.pymupdf4llm.to_markdown") as to_md:
                pages = extract_pdf("sample.pdf")

        assert len(pages) == 2
        assert pages[0].page_number == 1
        assert pages[0].metadata["extractor"] == "pymupdf"
        to_md.assert_not_called()
        doc.close.assert_called_once()

    def test_falls_back_to_single_pass_markdown(self):
        empty_page = MagicMock()
        empty_page.get_text.return_value = "   "

        doc = MagicMock()
        doc.__len__.return_value = 1
        doc.__getitem__.side_effect = lambda i: empty_page

        with patch("app.ingestion.extractors.pdf.pymupdf.open", return_value=doc):
            with patch(
                "app.ingestion.extractors.pdf.pymupdf4llm.to_markdown",
                return_value=[{"text": "OCR / layout text", "metadata": {"page": 0}}],
            ) as to_md:
                pages = extract_pdf("scanned.pdf")

        assert len(pages) == 1
        assert pages[0].text == "OCR / layout text"
        assert pages[0].metadata["extractor"] == "pymupdf4llm"
        to_md.assert_called_once_with("scanned.pdf", page_chunks=True)
