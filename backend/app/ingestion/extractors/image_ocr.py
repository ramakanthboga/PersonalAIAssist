"""Image OCR extraction using Tesseract."""

from __future__ import annotations

from app.core.logging import get_logger
from app.ingestion.extractors import ExtractedPage

logger = get_logger(__name__)

# Mitigate decompression-bomb DoS via crafted images.
_MAX_IMAGE_PIXELS = 40_000_000


def extract_image(file_path: str) -> list[ExtractedPage]:
    """Extract text from an image using OCR."""
    try:
        from PIL import Image
        import pytesseract
    except ImportError:
        logger.warning("ocr_unavailable", detail="pytesseract or Pillow not installed")
        return [ExtractedPage(
            text="[OCR not available – install pytesseract and Pillow]",
            page_number=1,
            metadata={"source_type": "image", "ocr_status": "unavailable"},
        )]

    Image.MAX_IMAGE_PIXELS = _MAX_IMAGE_PIXELS
    try:
        with Image.open(file_path) as image:
            image.load()
            text = pytesseract.image_to_string(image).strip()
    except Image.DecompressionBombError as exc:
        raise ValueError("Image is too large to process safely") from exc
    except pytesseract.TesseractNotFoundError:
        logger.warning("ocr_unavailable", detail="tesseract binary not found on PATH")
        return [ExtractedPage(
            text="[OCR not available – install the Tesseract binary]",
            page_number=1,
            metadata={"source_type": "image", "ocr_status": "unavailable"},
        )]
    except OSError as exc:
        raise ValueError(f"Failed to read image file: {exc}") from exc

    if not text:
        return [ExtractedPage(
            text="[No text detected in image]",
            page_number=1,
            metadata={"source_type": "image", "ocr_status": "empty"},
        )]

    return [ExtractedPage(
        text=text,
        page_number=1,
        metadata={"source_type": "image", "ocr_status": "success"},
    )]
