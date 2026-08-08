"""Document parsing dispatcher – routes files to the correct extractor."""

from __future__ import annotations

from pathlib import Path

from app.core.logging import get_logger
from app.ingestion.extractors import ExtractedPage
from app.ingestion.extractors.csv_excel import extract_csv, extract_excel
from app.ingestion.extractors.docx import extract_docx
from app.ingestion.extractors.image_ocr import extract_image
from app.ingestion.extractors.pdf import extract_pdf
from app.ingestion.extractors.text import extract_text

logger = get_logger(__name__)

_EXTRACTOR_MAP: dict[str, callable] = {
    ".pdf": extract_pdf,
    ".docx": extract_docx,
    ".txt": extract_text,
    ".md": extract_text,
    ".csv": extract_csv,
    ".xlsx": extract_excel,
    ".png": extract_image,
    ".jpg": extract_image,
    ".jpeg": extract_image,
    ".tif": extract_image,
    ".tiff": extract_image,
}


def parse_document(file_path: str) -> list[ExtractedPage]:
    """Parse a document file and return extracted pages.

    Raises ValueError for unsupported file types.
    """
    ext = Path(file_path).suffix.lower()
    extractor = _EXTRACTOR_MAP.get(ext)
    if extractor is None:
        raise ValueError(f"Unsupported file extension: {ext}")

    logger.info("parsing_document", file_path=file_path, extractor=ext)
    pages = extractor(file_path)
    logger.info("parsed_document", file_path=file_path, page_count=len(pages))
    return pages
