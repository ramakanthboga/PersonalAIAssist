"""OpenRouter LLM provider (OpenAI-compatible API)."""

from __future__ import annotations

from typing import AsyncIterator

from app.core.config import get_settings
from app.core.exceptions import LLMProviderError
from app.core.logging import get_logger
from app.llm.base import LLMProvider, LLMResponse, ModelInfo

logger = get_logger(__name__)

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


class OpenRouterProvider(LLMProvider):
    def __init__(self) -> None:
        settings = get_settings()
        if not settings.OPENROUTER_API_KEY:
            raise LLMProviderError("openrouter", "OPENROUTER_API_KEY is not set")

        from openai import AsyncOpenAI

        self._client = AsyncOpenAI(
            api_key=settings.OPENROUTER_API_KEY,
            base_url=OPENROUTER_BASE_URL,
        )
        self._default_model = settings.LLM_MODEL
        logger.info("openrouter_provider_init", model=self._default_model)

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
            logger.exception("openrouter_generate_failed")
            raise LLMProviderError("openrouter", str(exc))

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
            logger.exception("openrouter_stream_failed")
            raise LLMProviderError("openrouter", str(exc))

    async def list_models(self) -> list[ModelInfo]:
        try:
            import httpx

            async with httpx.AsyncClient() as client:
                resp = await client.get(f"{OPENROUTER_BASE_URL}/models")
                resp.raise_for_status()
                data = resp.json()
            return [
                ModelInfo(
                    id=m["id"],
                    name=m.get("name", m["id"]),
                    provider="openrouter",
                    max_tokens=m.get("context_length"),
                )
                for m in data.get("data", [])[:50]
            ]
        except Exception:
            logger.warning("openrouter_list_models_fallback")
            return [
                ModelInfo(id="openai/gpt-4o-mini", name="GPT-4o Mini", provider="openrouter"),
                ModelInfo(id="anthropic/claude-sonnet-4-20250514", name="Claude Sonnet 4", provider="openrouter"),
            ]

    async def health_check(self) -> bool:
        try:
            import httpx

            async with httpx.AsyncClient() as client:
                resp = await client.get(f"{OPENROUTER_BASE_URL}/models")
                return resp.status_code == 200
        except Exception:
            return False
