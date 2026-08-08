"""QA coverage for every supported document format extractor."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pymupdf
import pytest
from openpyxl import Workbook
from PIL import Image

from app.ingestion.parser import parse_document
from app.security.file_validator import (
    FileValidationError,
    content_type_for_extension,
    validate_magic_bytes,
    validate_upload,
)


def _write_pdf(path: Path, text: str = "Hello PDF format test") -> None:
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    doc.save(path)
    doc.close()


def _write_docx(path: Path, text: str = "Hello DOCX format test") -> None:
    # Minimal OOXML package without pulling in full python-docx write path quirks.
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/word/document.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
        "</Types>"
    )
    rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        'Target="word/document.xml"/>'
        "</Relationships>"
    )
    document = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body><w:p><w:r><w:t>{text}</w:t></w:r></w:p></w:body></w:document>"
    )
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("_rels/.rels", rels)
        zf.writestr("word/document.xml", document)


def _write_xlsx(path: Path) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    ws.append(["name", "value"])
    ws.append(["alpha", 1])
    ws.append(["beta", 2])
    wb.save(path)


def _write_png(path: Path) -> None:
    Image.new("RGB", (32, 32), color=(20, 120, 200)).save(path, format="PNG")


def _write_jpeg(path: Path) -> None:
    Image.new("RGB", (32, 32), color=(200, 80, 20)).save(path, format="JPEG")


def _write_tiff(path: Path) -> None:
    Image.new("RGB", (32, 32), color=(80, 200, 80)).save(path, format="TIFF")


@pytest.fixture
def sample_files(tmp_path: Path) -> dict[str, Path]:
    files = {
        "pdf": tmp_path / "sample.pdf",
        "docx": tmp_path / "sample.docx",
        "txt": tmp_path / "sample.txt",
        "md": tmp_path / "sample.md",
        "csv": tmp_path / "sample.csv",
        "xlsx": tmp_path / "sample.xlsx",
        "png": tmp_path / "sample.png",
        "jpg": tmp_path / "sample.jpg",
        "jpeg": tmp_path / "sample.jpeg",
        "tif": tmp_path / "sample.tif",
        "tiff": tmp_path / "sample.tiff",
    }
    _write_pdf(files["pdf"])
    _write_docx(files["docx"])
    files["txt"].write_text("Plain text format test\nLine two", encoding="utf-8")
    files["md"].write_text("# Markdown format test\n\nParagraph", encoding="utf-8")
    files["csv"].write_text("name,value\nalpha,1\nbeta,2\n", encoding="utf-8")
    _write_xlsx(files["xlsx"])
    _write_png(files["png"])
    _write_jpeg(files["jpg"])
    _write_jpeg(files["jpeg"])
    _write_tiff(files["tif"])
    _write_tiff(files["tiff"])
    return files


class TestSupportedFormatParsing:
    @pytest.mark.parametrize(
        "key,needle",
        [
            ("pdf", "Hello PDF"),
            ("docx", "Hello DOCX"),
            ("txt", "Plain text"),
            ("md", "Markdown"),
            ("csv", "alpha"),
            ("xlsx", "Sheet: Sheet1"),
        ],
    )
    def test_text_formats_extract_content(self, sample_files, key, needle):
        pages = parse_document(str(sample_files[key]))
        assert pages
        assert any(needle in p.text for p in pages)

    @pytest.mark.parametrize("key", ["png", "jpg", "jpeg", "tif", "tiff"])
    def test_image_formats_parse(self, sample_files, key):
        pages = parse_document(str(sample_files[key]))
        assert len(pages) == 1
        assert pages[0].metadata["source_type"] == "image"
        # OCR may be unavailable in CI; still must return a page, not raise.
        assert pages[0].metadata["ocr_status"] in {"success", "empty", "unavailable"}

    def test_unsupported_extension_raises(self, tmp_path: Path):
        bad = tmp_path / "notes.html"
        bad.write_text("<html>hi</html>", encoding="utf-8")
        with pytest.raises(ValueError, match="Unsupported"):
            parse_document(str(bad))


class TestFormatValidation:
    def test_all_supported_extensions_validate(self, sample_files):
        for path in sample_files.values():
            safe = validate_upload(path.name, path.read_bytes())
            assert Path(safe).suffix.lower() == path.suffix.lower()
            assert content_type_for_extension(path.suffix).startswith(
                ("application/", "text/", "image/")
            )

    def test_rejects_empty_file(self):
        with pytest.raises(FileValidationError, match="empty"):
            validate_upload("empty.txt", b"")

    def test_rejects_legacy_doc_extension(self):
        with pytest.raises(FileValidationError, match="not allowed"):
            validate_upload("resume.doc", b"\xd0\xcf\x11\xe0" + b"\x00" * 32)

    def test_rejects_legacy_xls_extension(self):
        with pytest.raises(FileValidationError, match="not allowed"):
            validate_upload("sheet.xls", b"\xd0\xcf\x11\xe0" + b"\x00" * 32)

    def test_rejects_polyglot_exe_as_pdf(self):
        with pytest.raises(FileValidationError, match="content does not match"):
            validate_magic_bytes(b"MZ\x90\x00fake-exe", ".pdf")

    def test_rejects_text_masquerading_as_png(self):
        with pytest.raises(FileValidationError, match="content does not match"):
            validate_upload("photo.png", b"this is not a png")

    def test_rejects_path_traversal_filename_keeps_basename(self, sample_files):
        content = sample_files["pdf"].read_bytes()
        safe = validate_upload("../../etc/passwd.pdf", content)
        assert safe == "passwd.pdf"
        assert ".." not in safe

    def test_rejects_null_byte_in_filename(self, sample_files):
        content = sample_files["txt"].read_bytes()
        safe = validate_upload("evil\x00.txt", content)
        assert "\x00" not in safe
