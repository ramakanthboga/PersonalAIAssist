"""Ensure OpenAPI / docs are not exposed outside development."""

from __future__ import annotations

from app.core.config import Environment, Settings


def test_docs_only_in_development():
    assert Settings.model_construct(ENVIRONMENT=Environment.DEVELOPMENT).expose_api_docs is True
    assert Settings.model_construct(ENVIRONMENT=Environment.STAGING).expose_api_docs is False
    assert Settings.model_construct(ENVIRONMENT=Environment.PRODUCTION).expose_api_docs is False


def test_registration_allowlist():
    settings = Settings.model_construct(
        ALLOW_REGISTRATION=True,
        REGISTRATION_ALLOWED_EMAILS=["you@gmail.com"],
    )
    assert settings.is_registration_allowed_for("you@gmail.com") is True
    assert settings.is_registration_allowed_for("other@gmail.com") is False

    closed = Settings.model_construct(ALLOW_REGISTRATION=False, REGISTRATION_ALLOWED_EMAILS=[])
    assert closed.is_registration_allowed_for("you@gmail.com") is False
