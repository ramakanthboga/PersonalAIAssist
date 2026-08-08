"""Anthropic LLM provider."""

from __future__ import annotations

from typing import AsyncIterator

from app.core.config import get_settings
from app.core.exceptions import LLMProviderError
from app.core.logging import get_logger
from app.llm.base import LLMProvider, LLMResponse, ModelInfo

logger = get_logger(__name__)


class AnthropicProvider(LLMProvider):
    def __init__(self) -> None:
        settings = get_settings()
        if not settings.ANTHROPIC_API_KEY:
            raise LLMProviderError("anthropic", "ANTHROPIC_API_KEY is not set")

        import anthropic
        self._client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
        self._default_model = settings.LLM_MODEL if "claude" in settings.LLM_MODEL else "claude-sonnet-4-20250514"
        logger.info("anthropic_provider_init", model=self._default_model)

    def _to_messages(self, prompt: str | list[dict[str, str]]) -> tuple[str, list[dict[str, str]]]:
        """Returns (system_message, user_messages) tuple for Anthropic API."""
        if isinstance(prompt, str):
            return "", [{"role": "user", "content": prompt}]
        system = ""
        messages = []
        for msg in prompt:
            if msg["role"] == "system":
                system = msg["content"]
            else:
                messages.append(msg)
        return system, messages

    async def generate(
        self,
        prompt: str | list[dict[str, str]],
        *,
        model: str | None = None,
        temperature: float = 0.1,
        max_tokens: int = 2048,
    ) -> LLMResponse:
        system, messages = self._to_messages(prompt)
        try:
            kwargs = {
                "model": model or self._default_model,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
            }
            if system:
                kwargs["system"] = system

            response = await self._client.messages.create(**kwargs)
            content = "".join(
                block.text for block in response.content if block.type == "text"
            )
            return LLMResponse(
                content=content,
                model=response.model,
                usage={
                    "prompt_tokens": response.usage.input_tokens,
                    "completion_tokens": response.usage.output_tokens,
                    "total_tokens": response.usage.input_tokens + response.usage.output_tokens,
                },
            )
        except Exception as exc:
            logger.exception("anthropic_generate_failed")
            raise LLMProviderError("anthropic", str(exc))

    async def stream(
        self,
        prompt: str | list[dict[str, str]],
        *,
        model: str | None = None,
        temperature: float = 0.1,
        max_tokens: int = 2048,
    ) -> AsyncIterator[str]:
        system, messages = self._to_messages(prompt)
        try:
            kwargs = {
                "model": model or self._default_model,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "stream": True,
            }
            if system:
                kwargs["system"] = system

            async with self._client.messages.stream(**{k: v for k, v in kwargs.items() if k != "stream"}) as stream:
                async for text in stream.text_stream:
                    yield text
        except Exception as exc:
            logger.exception("anthropic_stream_failed")
            raise LLMProviderError("anthropic", str(exc))

    async def list_models(self) -> list[ModelInfo]:
        return [
            ModelInfo(id="claude-sonnet-4-20250514", name="Claude Sonnet 4", provider="anthropic", max_tokens=8192),
            ModelInfo(id="claude-opus-4-20250514", name="Claude Opus 4", provider="anthropic", max_tokens=8192),
            ModelInfo(id="claude-3-5-haiku-20241022", name="Claude 3.5 Haiku", provider="anthropic", max_tokens=8192),
        ]

    async def health_check(self) -> bool:
        try:
            await self._client.messages.create(
                model=self._default_model,
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=5,
            )
            return True
        except Exception:
            return False
