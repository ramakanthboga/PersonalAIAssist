"""Runtime helpers for choosing an LLM provider in the current environment."""

from __future__ import annotations

import os
from pathlib import Path

from app.core.config import LLMProviderName, get_settings
from app.core.exceptions import LLMProviderError

# Chat providers that work in Docker (standard HTTP APIs).
DOCKER_CHAT_PROVIDERS: tuple[LLMProviderName, ...] = (
    LLMProviderName.OPENAI,
    LLMProviderName.ANTHROPIC,
    LLMProviderName.GEMINI,
    LLMProviderName.OPENROUTER,
)

CHAT_PROVIDER_ORDER: tuple[LLMProviderName, ...] = (
    LLMProviderName.CURSOR,
    *DOCKER_CHAT_PROVIDERS,
)


def is_running_in_docker() -> bool:
    """Return True when the backend is running inside a container."""
    return Path("/.dockerenv").exists() or os.environ.get("RUNNING_IN_DOCKER") == "1"


def is_cursor_proxy_configured() -> bool:
    """True when a host-side Cursor OpenAI proxy is configured."""
    settings = get_settings()
    return bool(settings.CURSOR_PROXY_URL and settings.CURSOR_API_KEY)


def is_cursor_supported() -> bool:
    """Cursor works via cloud agents in Docker, or local agents on the host."""
    settings = get_settings()
    if not settings.CURSOR_API_KEY:
        return False
    # Docker uses cloud agents (requires a linked GitHub repo or CURSOR_CLOUD_REPO).
    return True


def provider_has_key(name: LLMProviderName) -> bool:
    settings = get_settings()
    key_map: dict[LLMProviderName, str | None] = {
        LLMProviderName.CURSOR: settings.CURSOR_API_KEY,
        LLMProviderName.OPENAI: settings.OPENAI_API_KEY,
        LLMProviderName.ANTHROPIC: settings.ANTHROPIC_API_KEY,
        LLMProviderName.GEMINI: settings.GOOGLE_API_KEY,
        LLMProviderName.OPENROUTER: settings.OPENROUTER_API_KEY,
    }
    return bool(key_map.get(name))


def cursor_unavailable_message() -> str:
    return (
        "Cursor local agents are unavailable in this environment. "
        "For Docker, set CURSOR_CLOUD_REPO=https://github.com/owner/repo "
        "(a repo linked in your Cursor account) and LLM_PROVIDER=cursor, "
        "then recreate the backend. Host-only alternative: run .\\make.ps1 backend "
        "with Cursor IDE open."
    )


def resolve_chat_provider_name(
    requested: LLMProviderName | None = None,
) -> LLMProviderName:
    """Pick the best chat provider for the current runtime."""
    settings = get_settings()
    chosen = requested or settings.LLM_PROVIDER

    if chosen == LLMProviderName.CURSOR:
        if provider_has_key(LLMProviderName.CURSOR):
            return LLMProviderName.CURSOR
        if requested is not None:
            raise LLMProviderError("cursor", "CURSOR_API_KEY is not set")
        for candidate in DOCKER_CHAT_PROVIDERS:
            if provider_has_key(candidate):
                return candidate
        raise LLMProviderError("chat", "CURSOR_API_KEY is not set")

    if not provider_has_key(chosen):
        if requested is not None:
            raise LLMProviderError(chosen.value, f"{chosen.value.upper()}_API_KEY is not set")
        for candidate in CHAT_PROVIDER_ORDER:
            if provider_has_key(candidate):
                return candidate
        raise LLMProviderError(
            "chat",
            "No LLM API key is configured. Add CURSOR_API_KEY or OPENAI_API_KEY to .env.",
        )

    return chosen
