"""Unit tests for suggested prompt helpers."""

from __future__ import annotations

from app.rag.suggested_prompts import (
    _learning_goal,
    example_prompts_for_documents,
    format_suggested_prompts_markdown,
)


def test_example_prompts_include_filename():
    prompts = example_prompts_for_documents(["OWASP-Top-10.pdf"])
    assert any("OWASP" in p for p in prompts)
    assert any("Summarize" in p for p in prompts)


def test_learning_goal_extracted():
    assert _learning_goal("suggest prompt for learning agentic ai security") == (
        "agentic ai security"
    )


def test_example_prompts_respect_learning_goal():
    prompts = example_prompts_for_documents(
        ["OWASP-Top-10-for-Agentic-Applications.pdf"],
        user_query="suggest prompt for learning agentic ai security",
    )
    assert any("agentic" in p.lower() for p in prompts)
    assert any("Explain" in p or "learning" in p.lower() for p in prompts)


def test_format_suggested_prompts_markdown():
    text = format_suggested_prompts_markdown(
        ["OWASP-Top-10.pdf"],
        user_query="suggest prompts",
    )
    assert "OWASP" in text
    assert "prompts you can ask" in text.lower() or "here are prompts" in text.lower()
