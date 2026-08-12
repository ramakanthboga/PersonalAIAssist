"""Google OAuth must not auto-link onto existing password accounts."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.exceptions import ValidationError
from app.services.user_service import UserService


@pytest.mark.asyncio
async def test_google_does_not_auto_link_password_account():
    existing = MagicMock()
    existing.is_active = True
    existing.hashed_password = "hashed"
    existing.oauth_provider = None
    existing.oauth_sub = None

    repo = MagicMock()
    repo.get_by_oauth_sub = AsyncMock(return_value=None)
    repo.get_by_email = AsyncMock(return_value=existing)
    repo.create = AsyncMock()
    repo.update = AsyncMock()

    svc = UserService(db=MagicMock())
    svc._repo = repo

    with pytest.raises(ValidationError, match="already exists"):
        await svc.login_or_register_google(
            email="victim@example.com",
            email_verified=True,
            full_name="Victim",
            oauth_sub="google-sub-1",
        )

    repo.update.assert_not_called()
    repo.create.assert_not_called()


@pytest.mark.asyncio
async def test_google_creates_user_when_email_unused(monkeypatch: pytest.MonkeyPatch):
    from app.core.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "ALLOW_REGISTRATION", True)
    monkeypatch.setattr(settings, "REGISTRATION_ALLOWED_EMAILS", [])

    created = MagicMock()
    repo = MagicMock()
    repo.get_by_oauth_sub = AsyncMock(return_value=None)
    repo.get_by_email = AsyncMock(return_value=None)
    repo.create = AsyncMock(return_value=created)

    svc = UserService(db=MagicMock())
    svc._repo = repo

    user = await svc.login_or_register_google(
        email="new@example.com",
        email_verified=True,
        full_name="New User",
        oauth_sub="google-sub-2",
    )
    assert user is created
    repo.create.assert_awaited_once()
