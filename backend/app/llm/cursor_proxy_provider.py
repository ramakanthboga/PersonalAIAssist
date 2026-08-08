"""Cursor via OpenAI-compatible proxy (for Docker + host-side cursor-openai-api)."""

from __future__ import annotations

from typing import AsyncIterator

from app.core.config import get_settings
from app.core.exceptions import LLMProviderError
from app.core.logging import get_logger
from app.llm.base import LLMProvider, LLMResponse, ModelInfo
from app.security.error_sanitize import client_safe_llm_error

logger = get_logger(__name__)


class CursorProxyProvider(LLMProvider):
    """Talk to Cursor models through a host proxy exposing /v1/chat/completions."""

    def __init__(self) -> None:
        settings = get_settings()
        if not settings.CURSOR_PROXY_URL:
            raise LLMProviderError("cursor", "CURSOR_PROXY_URL is not set")
        if not settings.CURSOR_API_KEY:
            raise LLMProviderError("cursor", "CURSOR_API_KEY is not set")

        from openai import AsyncOpenAI

        self._client = AsyncOpenAI(
            api_key=settings.CURSOR_PROXY_AUTH_KEY or "not-needed",
            base_url=settings.CURSOR_PROXY_URL.rstrip("/"),
        )
        self._default_model = (
            settings.LLM_MODEL
            if settings.LLM_MODEL not in ("gpt-4o-mini", "gpt-4o")
            else "composer-2.5"
        )
        logger.info(
            "cursor_proxy_provider_init",
            model=self._default_model,
            base_url=settings.CURSOR_PROXY_URL,
        )

    def _to_messages(self, prompt: str | list[dict[str, str]]) -> list[dict[str, str]]:
        if isinstance(prompt, str):
            return [{"role": "user", "content": prompt}]
        return prompt

    async def generate(
        self,
        prompt: str | list[dict[str, str]],
        *,
        model: str | None = None,
        temperature: float = 0.1,
        max_tokens: int = 2048,
    ) -> LLMResponse:
        messages = self._to_messages(prompt)
        try:
            response = await self._client.chat.completions.create(
                model=model or self._default_model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            choice = response.choices[0]
            return LLMResponse(
                content=choice.message.content or "",
                model=response.model,
                usage={
                    "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                    "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                    "total_tokens": response.usage.total_tokens if response.usage else 0,
                },
            )
        except Exception as exc:
            logger.exception("cursor_proxy_generate_failed")
            raise LLMProviderError("cursor", client_safe_llm_error(exc))

    async def stream(
        self,
        prompt: str | list[dict[str, str]],
        *,
        model: str | None = None,
        temperature: float = 0.1,
        max_tokens: int = 2048,
    ) -> AsyncIterator[str]:
        messages = self._to_messages(prompt)
        try:
            response = await self._client.chat.completions.create(
                model=model or self._default_model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
            )
            async for chunk in response:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as exc:
            logger.exception("cursor_proxy_stream_failed")
            raise LLMProviderError("cursor", client_safe_llm_error(exc))

    async def list_models(self) -> list[ModelInfo]:
        try:
            models = await self._client.models.list()
            return [
                ModelInfo(id=m.id, name=m.id, provider="cursor")
                for m in models.data
            ]
        except Exception:
            return [
                ModelInfo(id="composer-2.5", name="Composer 2.5", provider="cursor"),
                ModelInfo(id="auto", name="Auto", provider="cursor"),
            ]

    async def health_check(self) -> bool:
        try:
            await self._client.models.list()
            return True
        except Exception:
            return False
