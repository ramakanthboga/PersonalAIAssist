"""Upload validation – file type, size, and magic bytes verification."""

from __future__ import annotations

from pathlib import Path

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Magic bytes for supported file types (text formats have no reliable signature)
_MAGIC_BYTES: dict[str, list[bytes]] = {
    ".pdf": [b"%PDF"],
    ".docx": [b"PK\x03\x04"],
    ".xlsx": [b"PK\x03\x04"],
    ".png": [b"\x89PNG"],
    ".jpg": [b"\xff\xd8\xff"],
    ".jpeg": [b"\xff\xd8\xff"],
    ".tif": [b"II\x2a\x00", b"MM\x00\x2a"],
    ".tiff": [b"II\x2a\x00", b"MM\x00\x2a"],
}

# Trusted content-types derived from extension (never trust client Content-Type alone)
_CONTENT_TYPES: dict[str, str] = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".csv": "text/csv",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".tif": "image/tiff",
    ".tiff": "image/tiff",
}


class FileValidationError(Exception):
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


def validate_file_extension(filename: str) -> str:
    """Validate file extension against allowed list. Returns the extension."""
    settings = get_settings()
    ext = Path(filename).suffix.lower()
    if ext not in settings.ALLOWED_EXTENSIONS:
        raise FileValidationError(f"File type '{ext}' is not allowed")
    return ext


def validate_file_size(size_bytes: int) -> None:
    """Validate file size against maximum."""
    settings = get_settings()
    if size_bytes > settings.max_upload_bytes:
        raise FileValidationError(
            f"File size ({size_bytes / 1024 / 1024:.1f} MB) "
            f"exceeds maximum of {settings.MAX_UPLOAD_SIZE_MB} MB"
        )
    if size_bytes == 0:
        raise FileValidationError("File is empty")


def validate_magic_bytes(content: bytes, extension: str) -> None:
    """Verify file content matches the claimed extension via magic bytes."""
    expected = _MAGIC_BYTES.get(extension.lower())
    if expected is None:
        return

    matches = any(content[:len(magic)] == magic for magic in expected)
    if not matches:
        logger.warning(
            "magic_bytes_mismatch",
            extension=extension,
            actual_bytes=content[:8].hex(),
        )
        raise FileValidationError(
            f"File content does not match extension '{extension}' — "
            "the file may be corrupted or misnamed"
        )


def validate_filename(filename: str, *, max_length: int = 255) -> str:
    """Sanitize and validate a filename."""
    import os
    import re

    name = os.path.basename(filename)
    name = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "_", name)
    name = re.sub(r"\.{2,}", ".", name)

    if not name or name.startswith("."):
        raise FileValidationError("Invalid filename")

    if len(name) > max_length:
        stem, ext = os.path.splitext(name)
        name = stem[:max_length - len(ext)] + ext

    return name


def content_type_for_extension(extension: str) -> str:
    """Return a trusted Content-Type for a validated extension."""
    return _CONTENT_TYPES.get(extension.lower(), "application/octet-stream")


def validate_upload(filename: str, content: bytes) -> str:
    """Run all validations on an uploaded file. Returns sanitized filename.

    Raises FileValidationError on any failure.
    """
    safe_name = validate_filename(filename)
    ext = validate_file_extension(safe_name)
    validate_file_size(len(content))
    validate_magic_bytes(content, ext)

    logger.info(
        "file_validated",
        filename=safe_name,
        extension=ext,
        size=len(content),
    )
    return safe_name
