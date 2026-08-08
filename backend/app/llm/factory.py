"""Provider factory – returns the configured LLM provider instance."""

from __future__ import annotations

import os

from app.core.config import LLMProviderName, get_settings
from app.core.logging import get_logger
from app.llm.base import LLMProvider
from app.llm.runtime import (
    is_cursor_proxy_configured,
    is_cursor_supported,
    provider_has_key,
    resolve_chat_provider_name,
)

logger = get_logger(__name__)


def get_llm_provider(name: LLMProviderName | None = None) -> LLMProvider:
    """Instantiate and return the requested (or default) LLM provider."""
    settings = get_settings()
    provider_name = name or settings.LLM_PROVIDER

    logger.info("creating_llm_provider", provider=provider_name.value)

    if provider_name == LLMProviderName.OPENAI:
        from app.llm.openai_provider import OpenAIProvider
        return OpenAIProvider()
    elif provider_name == LLMProviderName.ANTHROPIC:
        from app.llm.anthropic_provider import AnthropicProvider
        return AnthropicProvider()
    elif provider_name == LLMProviderName.GEMINI:
        from app.llm.gemini_provider import GeminiProvider
        return GeminiProvider()
    elif provider_name == LLMProviderName.CURSOR:
        from app.llm.cursor_provider import CursorProvider
        return CursorProvider()
    elif provider_name == LLMProviderName.OPENROUTER:
        from app.llm.openrouter_provider import OpenRouterProvider
        return OpenRouterProvider()
    else:
        raise ValueError(f"Unknown LLM provider: {provider_name}")


def get_chat_llm_provider(name: LLMProviderName | None = None) -> LLMProvider:
    """Return a chat provider. Prefer native Cursor cloud agents in Docker."""
    settings = get_settings()
    requested = name or settings.LLM_PROVIDER

    # Prefer native Cursor SDK (cloud in Docker). Host proxy is opt-in only.
    force_proxy = os.environ.get("CURSOR_FORCE_PROXY", "").lower() in ("1", "true", "yes")
    if (
        requested == LLMProviderName.CURSOR
        and force_proxy
        and is_cursor_proxy_configured()
    ):
        from app.llm.cursor_proxy_provider import CursorProxyProvider

        logger.info("creating_llm_provider", provider="cursor-proxy")
        return CursorProxyProvider()

    resolved = resolve_chat_provider_name(name)
    if resolved != requested:
        logger.warning(
            "llm_provider_fallback",
            requested=requested.value,
            resolved=resolved.value,
        )
    return get_llm_provider(resolved)


def get_available_providers() -> list[dict[str, str | bool]]:
    """Return a list of all providers with their configuration status."""
    settings = get_settings()
    key_map: dict[LLMProviderName, str | None] = {
        LLMProviderName.CURSOR: settings.CURSOR_API_KEY,
        LLMProviderName.OPENAI: settings.OPENAI_API_KEY,
        LLMProviderName.ANTHROPIC: settings.ANTHROPIC_API_KEY,
        LLMProviderName.GEMINI: settings.GOOGLE_API_KEY,
        LLMProviderName.OPENROUTER: settings.OPENROUTER_API_KEY,
    }
    return [
        {
            "id": name.value,
            "name": name.value.title(),
            "configured": bool(key) or (name == LLMProviderName.CURSOR and is_cursor_proxy_configured()),
            "available": (
                (name != LLMProviderName.CURSOR or is_cursor_supported() or is_cursor_proxy_configured())
            ),
            "active": name == settings.LLM_PROVIDER,
        }
        for name, key in key_map.items()
    ]
