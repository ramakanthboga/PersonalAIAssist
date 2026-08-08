"""Unit tests for RAG relevance filtering and abstain behavior."""

from __future__ import annotations

from types import SimpleNamespace

from app.rag.pipeline import _filter_by_min_score


def test_filter_by_min_score_uses_retrieval_score_without_rerank():
    settings = SimpleNamespace(MIN_RETRIEVAL_SCORE=0.42, MIN_RERANK_SCORE=0.25)
    chunks = [
        {"text": "a", "score": 0.55, "document_id": "d1"},
        {"text": "b", "score": 0.30, "document_id": "d1"},
    ]
    kept = _filter_by_min_score(chunks, settings)
    assert len(kept) == 1
    assert kept[0]["text"] == "a"


def test_filter_by_min_score_uses_rerank_score_when_present():
    settings = SimpleNamespace(MIN_RETRIEVAL_SCORE=0.42, MIN_RERANK_SCORE=0.25)
    chunks = [
        {"text": "a", "score": 0.9, "rerank_score": 0.1, "document_id": "d1"},
        {"text": "b", "score": 0.2, "rerank_score": 0.4, "document_id": "d1"},
    ]
    kept = _filter_by_min_score(chunks, settings)
    assert len(kept) == 1
    assert kept[0]["text"] == "b"


def test_filter_by_min_score_empty():
    settings = SimpleNamespace(MIN_RETRIEVAL_SCORE=0.42, MIN_RERANK_SCORE=0.25)
    assert _filter_by_min_score([], settings) == []
