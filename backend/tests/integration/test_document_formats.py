"""Integration + red-team tests for document upload format handling."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pymupdf
import pytest
from httpx import AsyncClient
from openpyxl import Workbook
from PIL import Image


async def _get_token(client: AsyncClient, email: str) -> str:
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "securepass123"},
    )
    assert resp.status_code == 201
    return resp.json()["access_token"]


def _pdf_bytes(text: str = "Upload PDF integration test") -> bytes:
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    data = doc.tobytes()
    doc.close()
    return data


def _docx_bytes(text: str = "Upload DOCX integration test") -> bytes:
    buf = io.BytesIO()
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
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("_rels/.rels", rels)
        zf.writestr("word/document.xml", document)
    return buf.getvalue()


def _xlsx_bytes() -> bytes:
    buf = io.BytesIO()
    wb = Workbook()
    ws = wb.active
    ws.append(["col", "n"])
    ws.append(["x", 1])
    wb.save(buf)
    return buf.getvalue()


def _png_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (16, 16), color=(10, 20, 30)).save(buf, format="PNG")
    return buf.getvalue()


def _jpeg_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (16, 16), color=(30, 20, 10)).save(buf, format="JPEG")
    return buf.getvalue()


def _tiff_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (16, 16), color=(40, 40, 40)).save(buf, format="TIFF")
    return buf.getvalue()


@pytest.fixture
def mock_ingest(monkeypatch):
    calls: list[tuple] = []

    def _fake_delay(document_id, file_path, user_id):
        calls.append((document_id, file_path, user_id))
        return None

    monkeypatch.setattr(
        "app.ingestion.tasks.ingest_document.delay",
        _fake_delay,
        raising=False,
    )
    # Import path used inside the route after local import.
    import app.ingestion.tasks as tasks

    monkeypatch.setattr(tasks.ingest_document, "delay", _fake_delay)
    return calls


@pytest.mark.asyncio
class TestAllFormatUploads:
    @pytest.mark.parametrize(
        "filename,content,mime,expected_type",
        [
            ("note.txt", b"hello text", "text/plain", "text/plain"),
            ("readme.md", b"# Title\nbody", "text/markdown", "text/markdown"),
            ("data.csv", b"a,b\n1,2\n", "text/csv", "text/csv"),
            ("doc.pdf", None, "application/pdf", "application/pdf"),
            ("letter.docx", None, "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
            ("sheet.xlsx", None, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
            ("pic.png", None, "image/png", "image/png"),
            ("pic.jpg", None, "image/jpeg", "image/jpeg"),
            ("pic.jpeg", None, "image/jpeg", "image/jpeg"),
            ("scan.tif", None, "image/tiff", "image/tiff"),
            ("scan.tiff", None, "image/tiff", "image/tiff"),
        ],
    )
    async def test_upload_supported_format(
        self,
        client: AsyncClient,
        mock_ingest,
        filename,
        content,
        mime,
        expected_type,
    ):
        if filename.endswith(".pdf"):
            content = _pdf_bytes()
        elif filename.endswith(".docx"):
            content = _docx_bytes()
        elif filename.endswith(".xlsx"):
            content = _xlsx_bytes()
        elif filename.endswith(".png"):
            content = _png_bytes()
        elif filename.endswith((".jpg", ".jpeg")):
            content = _jpeg_bytes()
        elif filename.endswith((".tif", ".tiff")):
            content = _tiff_bytes()

        token = await _get_token(client, f"fmt-{filename.replace('.', '-')}@test.com")
        resp = await client.post(
            "/api/v1/documents/upload",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": (filename, io.BytesIO(content), mime)},
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["original_filename"] == filename
        assert data["content_type"] == expected_type
        assert data["file_size"] == len(content)
        assert data["status"] == "pending"
        assert mock_ingest


@pytest.mark.asyncio
class TestUploadRedTeam:
    async def test_rejects_empty_file(self, client: AsyncClient, mock_ingest):
        token = await _get_token(client, "empty@test.com")
        resp = await client.post(
            "/api/v1/documents/upload",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": ("empty.txt", io.BytesIO(b""), "text/plain")},
        )
        assert resp.status_code == 400
        assert "empty" in resp.json()["detail"].lower()

    async def test_rejects_spoofed_pdf_extension(self, client: AsyncClient, mock_ingest):
        token = await _get_token(client, "spoof@test.com")
        resp = await client.post(
            "/api/v1/documents/upload",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": ("malware.pdf", io.BytesIO(b"MZ not a pdf"), "application/pdf")},
        )
        assert resp.status_code == 400
        assert "content does not match" in resp.json()["detail"]

    async def test_rejects_legacy_doc(self, client: AsyncClient, mock_ingest):
        token = await _get_token(client, "legacy-doc@test.com")
        resp = await client.post(
            "/api/v1/documents/upload",
            headers={"Authorization": f"Bearer {token}"},
            files={
                "file": (
                    "old.doc",
                    io.BytesIO(b"\xd0\xcf\x11\xe0" + b"\x00" * 64),
                    "application/msword",
                )
            },
        )
        assert resp.status_code == 400

    async def test_rejects_html_and_exe(self, client: AsyncClient, mock_ingest):
        token = await _get_token(client, "badext@test.com")
        for name, payload in [
            ("page.html", b"<script>alert(1)</script>"),
            ("hack.exe", b"MZ...."),
            ("data.json", b'{"a":1}'),
            ("deck.pptx", b"PK\x03\x04fake"),
        ]:
            resp = await client.post(
                "/api/v1/documents/upload",
                headers={"Authorization": f"Bearer {token}"},
                files={"file": (name, io.BytesIO(payload), "application/octet-stream")},
            )
            assert resp.status_code == 400, name

    async def test_path_traversal_filename_sanitized(
        self, client: AsyncClient, mock_ingest, tmp_path: Path
    ):
        token = await _get_token(client, "trav@test.com")
        content = _pdf_bytes()
        resp = await client.post(
            "/api/v1/documents/upload",
            headers={"Authorization": f"Bearer {token}"},
            files={
                "file": (
                    "../../../etc/passwd.pdf",
                    io.BytesIO(content),
                    "application/pdf",
                )
            },
        )
        assert resp.status_code == 201
        assert resp.json()["original_filename"] == "passwd.pdf"
        # Stored name is UUID-based, never the attacker path.
        assert ".." not in resp.json()["filename"]
        assert resp.json()["filename"].endswith(".pdf")

    async def test_ignores_spoofed_content_type_header(
        self, client: AsyncClient, mock_ingest
    ):
        token = await _get_token(client, "ctype@test.com")
        resp = await client.post(
            "/api/v1/documents/upload",
            headers={"Authorization": f"Bearer {token}"},
            files={
                "file": (
                    "notes.md",
                    io.BytesIO(b"# trusted type"),
                    "application/x-msdownload",
                )
            },
        )
        assert resp.status_code == 201
        assert resp.json()["content_type"] == "text/markdown"
