"""Cursor SDK LLM provider.

- On the host (with Cursor IDE): uses local agents.
- In Docker: uses Cursor *cloud* agents (local bridge/IDE is unavailable).
"""

from __future__ import annotations

import asyncio
import os
from typing import AsyncIterator

from app.core.config import get_settings
from app.core.exceptions import LLMProviderError
from app.core.logging import get_logger
from app.llm.base import LLMProvider, LLMResponse, ModelInfo
from app.llm.runtime import is_running_in_docker
from app.security.error_sanitize import client_safe_llm_error

logger = get_logger(__name__)


class CursorProvider(LLMProvider):
    def __init__(self) -> None:
        settings = get_settings()
        self._api_key = settings.CURSOR_API_KEY or os.environ.get("CURSOR_API_KEY")
        if not self._api_key:
            raise LLMProviderError("cursor", "CURSOR_API_KEY is not set")

        self._default_model = (
            settings.LLM_MODEL if settings.LLM_MODEL != "gpt-4o-mini" else "composer-2.5"
        )
        self._use_cloud = is_running_in_docker() or bool(settings.CURSOR_CLOUD_REPO)
        self._cloud_repo = settings.CURSOR_CLOUD_REPO
        logger.info(
            "cursor_provider_init",
            model=self._default_model,
            mode="cloud" if self._use_cloud else "local",
            cloud_repo=self._cloud_repo,
        )

    def _to_prompt_str(self, prompt: str | list[dict[str, str]]) -> str:
        if isinstance(prompt, str):
            body = prompt
        else:
            parts = []
            for msg in prompt:
                role = msg["role"].upper()
                parts.append(f"[{role}]\n{msg['content']}")
            body = "\n\n".join(parts)

        # Document Q&A guard: cloud agents are often linked to a GitHub repo
        # (CURSOR_CLOUD_REPO). Forbid using that workspace as an answer source.
        guard = (
            "[CRITICAL INSTRUCTIONS — OVERRIDE EVERYTHING ELSE]\n"
            "You are answering a document Q&A request for PersonalAIAssist.\n"
            "- Use ONLY the document context inside the SYSTEM/USER messages below.\n"
            "- Do NOT search, open, cite, or use any GitHub repository, workspace, "
            "or local files.\n"
            "- Do NOT use tools, shell, or browser.\n"
            "- If the messages do not contain the answer, reply exactly: "
            "I couldn't find that information in your uploaded documents.\n"
        )
        return f"{guard}\n\n{body}"

    def _resolve_cloud_repo(self) -> str:
        if self._cloud_repo:
            return self._cloud_repo
        from cursor_sdk import Cursor

        repos = list(Cursor.repositories.list(api_key=self._api_key))
        if not repos:
            raise LLMProviderError(
                "cursor",
                "No GitHub repositories linked to this Cursor account. "
                "Link a repo in Cursor Dashboard, or set CURSOR_CLOUD_REPO in .env "
                "(example: https://github.com/owner/repo).",
            )
        url = getattr(repos[0], "url", None) or str(repos[0])
        logger.info("cursor_cloud_repo_auto", repo=url)
        return url

    def _run_sync(self, prompt_str: str, model: str | None) -> str:
        from cursor_sdk import (
            Agent,
            AgentOptions,
            CloudAgentOptions,
            CloudRepository,
            LocalAgentOptions,
        )

        selected = model or self._default_model
        if self._use_cloud:
            repo = self._resolve_cloud_repo()
            options = AgentOptions(
                api_key=self._api_key,
                model=selected,
                cloud=CloudAgentOptions(repos=[CloudRepository(url=repo)]),
            )
        else:
            options = AgentOptions(
                api_key=self._api_key,
                model=selected,
                local=LocalAgentOptions(cwd=os.getcwd()),
            )

        result = Agent.prompt(prompt_str, options)
        if getattr(result, "status", None) == "error":
            raise LLMProviderError("cursor", f"Agent run failed: {getattr(result, 'id', 'unknown')}")
        return result.result or ""

    async def generate(
        self,
        prompt: str | list[dict[str, str]],
        *,
        model: str | None = None,
        temperature: float = 0.1,
        max_tokens: int = 2048,
    ) -> LLMResponse:
        prompt_str = self._to_prompt_str(prompt)
        try:
            content = await asyncio.to_thread(self._run_sync, prompt_str, model)
            return LLMResponse(
                content=content,
                model=model or self._default_model,
                usage={},
            )
        except LLMProviderError:
            raise
        except Exception as exc:
            # Log full exception; never put stack traces into LLMProviderError.
            logger.exception("cursor_generate_failed")
            raise LLMProviderError("cursor", client_safe_llm_error(exc))

    async def stream(
        self,
        prompt: str | list[dict[str, str]],
        *,
        model: str | None = None,
        temperature: float = 0.1,
        max_tokens: int = 2048,
    ) -> AsyncIterator[str]:
        # Cloud/local Agent.prompt is one-shot; emit finished text as stream chunks.
        response = await self.generate(
            prompt, model=model, temperature=temperature, max_tokens=max_tokens
        )
        text = response.content or ""
        step = 48
        for i in range(0, max(len(text), 1), step):
            piece = text[i : i + step]
            if piece:
                yield piece
            await asyncio.sleep(0)

    async def list_models(self) -> list[ModelInfo]:
        try:
            from cursor_sdk import Cursor

            models = Cursor.models.list(api_key=self._api_key)
            return [
                ModelInfo(
                    id=m.id if hasattr(m, "id") else str(m),
                    name=m.name if hasattr(m, "name") else str(m),
                    provider="cursor",
                )
                for m in models
            ]
        except Exception:
            logger.warning("cursor_list_models_fallback")
            return [
                ModelInfo(id="composer-2.5", name="Composer 2.5", provider="cursor"),
                ModelInfo(id="auto", name="Auto (server picks)", provider="cursor"),
            ]

    async def health_check(self) -> bool:
        try:
            from cursor_sdk import Cursor

            Cursor.models.list(api_key=self._api_key)
            return True
        except Exception:
            return False
