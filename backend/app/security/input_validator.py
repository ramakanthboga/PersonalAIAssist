"""Prompt injection detection and input sanitization."""

from __future__ import annotations

import re

from app.core.logging import get_logger

logger = get_logger(__name__)

_INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?previous\s+instructions",
    r"ignore\s+(all\s+)?above\s+instructions",
    r"disregard\s+(all\s+)?(previous|prior|above)",
    r"forget\s+(all\s+)?(previous|prior|above)",
    r"you\s+are\s+now\s+a",
    r"act\s+as\s+(if\s+you\s+are\s+)?a",
    r"pretend\s+(you\s+are|to\s+be)",
    r"new\s+instructions?\s*:",
    r"system\s*:\s*",
    r"\[system\]",
    r"\[INST\]",
    r"<\|im_start\|>",
    r"<\|endoftext\|>",
    r"<\|system\|>",
    r"###\s*instruction",
    r"override\s+(the\s+)?(system|prompt)",
    r"reveal\s+(your|the)\s+(system\s+)?prompt",
    r"show\s+(me\s+)?(your|the)\s+(system\s+)?prompt",
    r"what\s+(is|are)\s+your\s+(system\s+)?instructions",
    r"output\s+(your|the)\s+(system\s+)?prompt",
    r"repeat\s+(your|the)\s+(system\s+)?prompt",
    r"print\s+(your|the)\s+(system\s+)?prompt",
]

_COMPILED_PATTERNS = [re.compile(p, re.IGNORECASE) for p in _INJECTION_PATTERNS]


def detect_prompt_injection(text: str) -> bool:
    """Return True if the text contains suspected prompt injection patterns."""
    for pattern in _COMPILED_PATTERNS:
        if pattern.search(text):
            logger.warning(
                "prompt_injection_detected",
                pattern=pattern.pattern,
                text_preview=text[:100],
            )
            return True
    return False


def sanitize_input(text: str, *, max_length: int = 10000) -> str:
    """Sanitize user input by removing control characters and limiting length."""
    cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    cleaned = re.sub(r"\n{4,}", "\n\n\n", cleaned)
    cleaned = re.sub(r" {10,}", "  ", cleaned)
    if len(cleaned) > max_length:
        cleaned = cleaned[:max_length]
    return cleaned.strip()


def validate_chat_input(text: str) -> tuple[str, list[str]]:
    """Validate and sanitize chat input. Returns (sanitized_text, warnings).

    Raises ValueError if input is dangerous.
    """
    warnings: list[str] = []

    sanitized = sanitize_input(text)

    if not sanitized:
        raise ValueError("Message cannot be empty")

    if detect_prompt_injection(sanitized):
        raise ValueError(
            "Your message was flagged as a potential prompt injection attempt. "
            "Please rephrase your question."
        )

    if len(sanitized) > 5000:
        warnings.append("Message was truncated to 5000 characters")
        sanitized = sanitized[:5000]

    return sanitized, warnings
