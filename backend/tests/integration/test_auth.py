"""Integration tests for auth endpoints."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.core.config import get_settings


@pytest.mark.asyncio
class TestAuthEndpoints:
    async def test_register_success(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/auth/register",
            json={"email": "test@example.com", "password": "securepass123"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    async def test_register_disabled(self, client: AsyncClient, monkeypatch: pytest.MonkeyPatch):
        settings = get_settings()
        monkeypatch.setattr(settings, "ALLOW_REGISTRATION", False)
        resp = await client.post(
            "/api/v1/auth/register",
            json={"email": "blocked@example.com", "password": "securepass123"},
        )
        assert resp.status_code == 422
        assert "disabled" in resp.json()["detail"].lower()

    async def test_auth_providers_flags(self, client: AsyncClient):
        resp = await client.get("/api/v1/auth/providers")
        assert resp.status_code == 200
        data = resp.json()
        assert "google" in data
        assert "registration_enabled" in data

    async def test_register_duplicate(self, client: AsyncClient):
        await client.post(
            "/api/v1/auth/register",
            json={"email": "dup@example.com", "password": "securepass123"},
        )
        resp = await client.post(
            "/api/v1/auth/register",
            json={"email": "dup@example.com", "password": "securepass123"},
        )
        assert resp.status_code == 422

    async def test_login_success(self, client: AsyncClient):
        await client.post(
            "/api/v1/auth/register",
            json={"email": "login@example.com", "password": "securepass123"},
        )
        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "login@example.com", "password": "securepass123"},
        )
        assert resp.status_code == 200
        assert "access_token" in resp.json()

    async def test_login_wrong_password(self, client: AsyncClient):
        await client.post(
            "/api/v1/auth/register",
            json={"email": "wrong@example.com", "password": "securepass123"},
        )
        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "wrong@example.com", "password": "wrongpassword"},
        )
        assert resp.status_code == 401

    async def test_me_authenticated(self, client: AsyncClient):
        reg = await client.post(
            "/api/v1/auth/register",
            json={"email": "me@example.com", "password": "securepass123"},
        )
        token = reg.json()["access_token"]
        resp = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["email"] == "me@example.com"

    async def test_me_unauthenticated(self, client: AsyncClient):
        resp = await client.get("/api/v1/auth/me")
        assert resp.status_code == 403

    async def test_refresh_token(self, client: AsyncClient):
        reg = await client.post(
            "/api/v1/auth/register",
            json={"email": "refresh@example.com", "password": "securepass123"},
        )
        refresh = reg.json()["refresh_token"]
        resp = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh},
        )
        assert resp.status_code == 200
        assert "access_token" in resp.json()

    async def test_health(self, client: AsyncClient):
        resp = await client.get("/api/v1/health")
        assert resp.status_code == 200
        assert resp.json()["status"] in ("healthy", "degraded")
