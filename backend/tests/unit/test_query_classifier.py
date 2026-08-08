"""Unit tests for query classifier."""

from __future__ import annotations

from app.rag.query_classifier import classify_query, QueryType


class TestQueryClassifier:
    def test_lookup_pan(self):
        assert classify_query("What is my PAN number?") == QueryType.LOOKUP

    def test_lookup_expiry(self):
        assert classify_query("When does my passport expire?") == QueryType.LOOKUP

    def test_synthesis_summarize(self):
        assert classify_query("Summarize my insurance policy") == QueryType.SYNTHESIS

    def test_synthesis_explain(self):
        assert classify_query("Explain my tax returns") == QueryType.SYNTHESIS

    def test_comparison(self):
        assert classify_query("Compare Resume V1 with Resume V2") == QueryType.COMPARISON

    def test_comparison_vs(self):
        assert classify_query("Policy A vs Policy B") == QueryType.COMPARISON

    def test_listing_show_all(self):
        assert classify_query("Show all my tax documents") == QueryType.LISTING

    def test_listing_how_many(self):
        assert classify_query("How many documents do I have?") == QueryType.LISTING

    def test_list_content_is_not_document_inventory(self):
        # "list out top 10 ..." is content Q&A, not "list my documents"
        assert classify_query("list out top 10 owasp and provide with some examples") == QueryType.GENERAL

    def test_help_suggest_prompts(self):
        assert classify_query("how prompts i can provide. please suggest few prompts") == QueryType.HELP

    def test_help_suggest_prompt_for_learning_topic(self):
        assert (
            classify_query("suggest prompt for learning agentic ai security")
            == QueryType.HELP
        )

    def test_help_what_can_i_ask(self):
        assert classify_query("What can I ask?") == QueryType.HELP

    def test_general(self):
        assert classify_query("Hello, how are you?") == QueryType.GENERAL
