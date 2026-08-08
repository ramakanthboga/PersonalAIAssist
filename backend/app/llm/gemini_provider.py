"""Google Gemini LLM provider."""

from __future__ import annotations

from typing import AsyncIterator

from app.core.config import get_settings
from app.core.exceptions import LLMProviderError
from app.core.logging import get_logger
from app.llm.base import LLMProvider, LLMResponse, ModelInfo

logger = get_logger(__name__)


class GeminiProvider(LLMProvider):
    def __init__(self) -> None:
        settings = get_settings()
        if not settings.GOOGLE_API_KEY:
            raise LLMProviderError("gemini", "GOOGLE_API_KEY is not set")

        from google import genai
        self._client = genai.Client(api_key=settings.GOOGLE_API_KEY)
        self._default_model = settings.LLM_MODEL if "gemini" in settings.LLM_MODEL else "gemini-2.0-flash"
        logger.info("gemini_provider_init", model=self._default_model)

    def _to_content(self, prompt: str | list[dict[str, str]]) -> tuple[str | None, str]:
        """Returns (system_instruction, user_content)."""
        if isinstance(prompt, str):
            return None, prompt
        system = None
        user_parts = []
        for msg in prompt:
            if msg["role"] == "system":
                system = msg["content"]
            else:
                user_parts.append(msg["content"])
        return system, "\n\n".join(user_parts)

    async def generate(
        self,
        prompt: str | list[dict[str, str]],
        *,
        model: str | None = None,
        temperature: float = 0.1,
        max_tokens: int = 2048,
    ) -> LLMResponse:
        system, content = self._to_content(prompt)
        try:
            from google.genai import types

            config = types.GenerateContentConfig(
                temperature=temperature,
                max_output_tokens=max_tokens,
            )
            if system:
                config.system_instruction = system

            response = self._client.models.generate_content(
                model=model or self._default_model,
                contents=content,
                config=config,
            )
            return LLMResponse(
                content=response.text or "",
                model=model or self._default_model,
                usage={
                    "prompt_tokens": getattr(response.usage_metadata, "prompt_token_count", 0) or 0,
                    "completion_tokens": getattr(response.usage_metadata, "candidates_token_count", 0) or 0,
                    "total_tokens": getattr(response.usage_metadata, "total_token_count", 0) or 0,
                },
            )
        except Exception as exc:
            logger.exception("gemini_generate_failed")
            raise LLMProviderError("gemini", str(exc))

    async def stream(
        self,
        prompt: str | list[dict[str, str]],
        *,
        model: str | None = None,
        temperature: float = 0.1,
        max_tokens: int = 2048,
    ) -> AsyncIterator[str]:
        system, content = self._to_content(prompt)
        try:
            from google.genai import types

            config = types.GenerateContentConfig(
                temperature=temperature,
                max_output_tokens=max_tokens,
            )
            if system:
                config.system_instruction = system

            response = self._client.models.generate_content_stream(
                model=model or self._default_model,
                contents=content,
                config=config,
            )
            for chunk in response:
                if chunk.text:
                    yield chunk.text
        except Exception as exc:
            logger.exception("gemini_stream_failed")
            raise LLMProviderError("gemini", str(exc))

    async def list_models(self) -> list[ModelInfo]:
        return [
            ModelInfo(id="gemini-2.0-flash", name="Gemini 2.0 Flash", provider="gemini"),
            ModelInfo(id="gemini-2.5-pro-preview-06-05", name="Gemini 2.5 Pro", provider="gemini"),
            ModelInfo(id="gemini-2.5-flash-preview-05-20", name="Gemini 2.5 Flash", provider="gemini"),
        ]

    async def health_check(self) -> bool:
        try:
            self._client.models.generate_content(
                model=self._default_model,
                contents="ping",
            )
            return True
        except Exception:
            return False
