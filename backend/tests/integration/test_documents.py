"""Integration tests for document endpoints."""

from __future__ import annotations

import io

import pytest
from httpx import AsyncClient


async def _get_token(client: AsyncClient, email: str = "doc@test.com") -> str:
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "securepass123"},
    )
    return resp.json()["access_token"]


@pytest.fixture
def mock_ingest(monkeypatch):
    def _fake_delay(*_args, **_kwargs):
        return None

    import app.ingestion.tasks as tasks

    monkeypatch.setattr(tasks.ingest_document, "delay", _fake_delay)


@pytest.mark.asyncio
class TestDocumentEndpoints:
    async def test_upload_success(self, client: AsyncClient, mock_ingest):
        token = await _get_token(client)
        resp = await client.post(
            "/api/v1/documents/upload",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": ("test.txt", io.BytesIO(b"Hello world"), "text/plain")},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["original_filename"] == "test.txt"
        assert data["content_type"] == "text/plain"
        assert data["status"] == "pending"

    async def test_list_documents(self, client: AsyncClient, mock_ingest):
        token = await _get_token(client, "list@test.com")
        await client.post(
            "/api/v1/documents/upload",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": ("a.txt", io.BytesIO(b"content"), "text/plain")},
        )
        resp = await client.get(
            "/api/v1/documents/",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1

    async def test_delete_document(self, client: AsyncClient, mock_ingest):
        token = await _get_token(client, "del@test.com")
        upload = await client.post(
            "/api/v1/documents/upload",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": ("del.txt", io.BytesIO(b"delete me"), "text/plain")},
        )
        doc_id = upload.json()["id"]
        resp = await client.delete(
            f"/api/v1/documents/{doc_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 204

    async def test_upload_forbidden_extension(self, client: AsyncClient, mock_ingest):
        token = await _get_token(client, "ext@test.com")
        resp = await client.post(
            "/api/v1/documents/upload",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": ("hack.exe", io.BytesIO(b"MZ..."), "application/octet-stream")},
        )
        assert resp.status_code == 400

    async def test_cross_user_isolation(self, client: AsyncClient, mock_ingest):
        token1 = await _get_token(client, "user1@test.com")
        token2 = await _get_token(client, "user2@test.com")
        upload = await client.post(
            "/api/v1/documents/upload",
            headers={"Authorization": f"Bearer {token1}"},
            files={"file": ("private.txt", io.BytesIO(b"secret"), "text/plain")},
        )
        doc_id = upload.json()["id"]
        resp = await client.get(
            f"/api/v1/documents/{doc_id}",
            headers={"Authorization": f"Bearer {token2}"},
        )
        assert resp.status_code == 404

    async def test_clear_all_documents(self, client: AsyncClient, monkeypatch, mock_ingest):
        monkeypatch.setattr(
            "app.vectorstore.collections.delete_user_vectors",
            lambda user_id: None,
        )
        token = await _get_token(client, "clear@test.com")
        await client.post(
            "/api/v1/documents/upload",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": ("keep.txt", io.BytesIO(b"content"), "text/plain")},
        )
        resp = await client.delete(
            "/api/v1/documents/clear",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["deleted_documents"] >= 1

        listed = await client.get(
            "/api/v1/documents/",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert listed.json()["total"] == 0