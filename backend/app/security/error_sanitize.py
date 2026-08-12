"""Sanitize exceptions before returning them to end-user clients.

Full exception text (stack traces, container paths, SDK argv) stays in
server logs only. Clients get a short, non-sensitive message.
"""

from __future__ import annotations

import re
from typing import Any

# Indicators that a string is an internal diagnostic dump, not a safe copy.
_SENSITIVE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"traceback\s*\(most recent call last\)", re.I),
    re.compile(r"\bat\s+\S+\s+\([^)]+\.(?:py|js|ts):\d+", re.I),
    re.compile(r"file:///"),
    re.compile(r"/usr/local/lib/"),
    re.compile(r"/site-packages/"),
    re.compile(r"\\site-packages\\"),
    re.compile(r"node:internal/"),
    re.compile(r"cursor-sdk-bridge"),
    re.compile(r"--tool-callback-auth-token"),
    re.compile(r"ModuleJob\.run"),
    re.compile(r"\n\s+at\s+"),
)

_DEFAULT_CLIENT_MESSAGE = "Something went wrong. Please try again."
_LLM_CLIENT_MESSAGE = (
    "The AI service is temporarily unavailable. Please try again in a moment."
)
_RAG_CLIENT_MESSAGE = "Failed to process your question. Please try again."

# Map known internal failure fingerprints → safe, actionable client text.
_KNOWN_SAFE_MESSAGES: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(r"tool-callback-auth-token|Bridge exited|cursor-sdk-bridge", re.I),
        "The Cursor AI service could not start in this environment. "
        "Try again later, or switch LLM_PROVIDER to openai/anthropic/gemini "
        "in your .env if Cursor cloud agents are unavailable.",
    ),
    (
        re.compile(r"CURSOR_API_KEY is not set", re.I),
        "Cursor is not configured. Set CURSOR_API_KEY or choose another LLM provider.",
    ),
    (
        re.compile(r"No GitHub repositories linked|CURSOR_CLOUD_REPO", re.I),
        "Cursor cloud agents need a linked GitHub repo. "
        "Set CURSOR_CLOUD_REPO in .env, or use another LLM provider.",
    ),
    (
        re.compile(r"WinError 10038|local agents are unavailable", re.I),
        "Cursor local agents are unavailable here. "
        "Use cloud mode (CURSOR_CLOUD_REPO) or another LLM provider.",
    ),
    (
        re.compile(r"resource_exhausted|RateLimitError", re.I),
        "Cursor's usage limit for this account was reached. Wait a few minutes and "
        "try again, check your usage/billing in the Cursor dashboard, or switch "
        "LLM_PROVIDER to openai/anthropic/gemini/openrouter in .env in the meantime.",
    ),
    (
        re.compile(r"rate limit|429", re.I),
        "The AI service rate limit was reached. Please wait a moment and try again.",
    ),
    (
        re.compile(r"Authentication failed|Invalid or expired|401", re.I),
        "Authentication failed. Please sign in again.",
    ),
)


def looks_like_internal_error(text: str) -> bool:
    """Return True if text appears to contain stack traces or internal paths."""
    if not text:
        return False
    if len(text) > 400:
        return True
    return any(pat.search(text) for pat in _SENSITIVE_PATTERNS)


def client_safe_error_message(
    exc: BaseException | str | None,
    *,
    fallback: str = _DEFAULT_CLIENT_MESSAGE,
) -> str:
    """Return a user-safe error string; never include stack traces or paths."""
    if exc is None:
        return fallback

    raw = str(exc).strip() if not isinstance(exc, str) else exc.strip()
    if not raw:
        return fallback

    for pattern, message in _KNOWN_SAFE_MESSAGES:
        if pattern.search(raw):
            return message

    # Allow short, already-safe AppError-style messages (no internals).
    if not looks_like_internal_error(raw) and len(raw) <= 280:
        # Strip provider prefix noise like "[cursor] " only when internals remain;
        # keep concise provider tags for known safe messages.
        return raw

    if "llm" in fallback.lower() or "ai service" in fallback.lower():
        return fallback
    return fallback


def client_safe_llm_error(exc: BaseException | str | None) -> str:
    return client_safe_error_message(exc, fallback=_LLM_CLIENT_MESSAGE)


def client_safe_rag_error(exc: BaseException | str | None) -> str:
    return client_safe_error_message(exc, fallback=_RAG_CLIENT_MESSAGE)


def public_detail_from_exc(exc: Any, *, fallback: str = _DEFAULT_CLIENT_MESSAGE) -> str:
    """Prefer AppError.message when safe; otherwise sanitize."""
    message = getattr(exc, "message", None)
    if isinstance(message, str) and message.strip():
        return client_safe_error_message(message, fallback=fallback)
    return client_safe_error_message(exc, fallback=fallback)
