"""RagChatbot: real TF-IDF embedder + real local chromadb, wired into Ch35's
retrieve -> ground -> (simulated) generate -> monitor pattern.
"""

from __future__ import annotations

import pytest

from lab import RagChatbot


def test_chat_before_load_documents_raises(store_dir) -> None:
    bot = RagChatbot(store_dir)
    with pytest.raises(RuntimeError, match="load_documents"):
        bot.chat("hello")


def test_retrieve_before_load_documents_raises(store_dir) -> None:
    bot = RagChatbot(store_dir)
    with pytest.raises(RuntimeError, match="load_documents"):
        bot.retrieve("hello")


def test_load_documents_requires_at_least_one(store_dir) -> None:
    bot = RagChatbot(store_dir)
    with pytest.raises(ValueError):
        bot.load_documents([])


def test_load_documents_populates_the_store(store_dir, knowledge_base) -> None:
    bot = RagChatbot(store_dir)
    bot.load_documents(knowledge_base)
    assert bot.store.count() == len(knowledge_base)


def test_chat_on_relevant_query_is_grounded(store_dir, knowledge_base) -> None:
    bot = RagChatbot(store_dir)
    bot.load_documents(knowledge_base)

    result = bot.chat("How many requests per minute am I allowed before I get a 429?")

    assert result["grounded"] is True
    assert result["similarity"] >= bot.SIM_THRESHOLD
    assert "rate-limits" in result["sources"]
    assert "rate-limits" in result["answer"]


def test_chat_on_unrelated_query_is_not_grounded(store_dir, knowledge_base) -> None:
    bot = RagChatbot(store_dir)
    bot.load_documents(knowledge_base)

    result = bot.chat("What is the tallest mountain in South America?")

    assert result["grounded"] is False
    assert result["similarity"] < bot.SIM_THRESHOLD
    assert result["sources"] == []
    assert "don't know" in result["answer"]


def test_chat_rejects_empty_query(store_dir, knowledge_base) -> None:
    bot = RagChatbot(store_dir)
    bot.load_documents(knowledge_base)
    with pytest.raises(ValueError):
        bot.chat("   ")


def test_chat_prompt_contains_the_question(store_dir, knowledge_base) -> None:
    bot = RagChatbot(store_dir)
    bot.load_documents(knowledge_base)
    result = bot.chat("How do refund amounts get credited back to the customer?")
    assert "How do refund amounts get credited back to the customer?" in result["prompt"]


def test_retrieve_respects_top_k(store_dir, knowledge_base) -> None:
    bot = RagChatbot(store_dir)
    bot.load_documents(knowledge_base)
    results = bot.retrieve("How does the API handle authentication and refunds?", top_k=2)
    assert len(results) == 2


def test_health_report_counts_grounded_and_ungrounded(store_dir, knowledge_base) -> None:
    bot = RagChatbot(store_dir)
    bot.load_documents(knowledge_base)

    bot.chat("How do I authenticate my requests with an API key?")
    bot.chat("What events can I subscribe to with webhooks?")
    bot.chat("What is the population of Antarctica?")

    report = bot.health_report()
    assert report["requests"] == 3
    assert report["grounded_responses"] == 2
    assert report["ungrounded_responses"] == 1
    assert report["errors"] == 0
    assert report["grounded_rate"] == pytest.approx(2 / 3)


def test_health_report_counts_errors_from_empty_queries(store_dir, knowledge_base) -> None:
    bot = RagChatbot(store_dir)
    bot.load_documents(knowledge_base)

    with pytest.raises(ValueError):
        bot.chat("")

    report = bot.health_report()
    assert report["requests"] == 1
    assert report["errors"] == 1
    assert report["grounded_responses"] == 0
    assert report["ungrounded_responses"] == 0


def test_health_report_before_any_chat_is_all_zero(store_dir, knowledge_base) -> None:
    bot = RagChatbot(store_dir)
    bot.load_documents(knowledge_base)
    report = bot.health_report()
    assert report == {
        "requests": 0,
        "grounded_responses": 0,
        "ungrounded_responses": 0,
        "errors": 0,
        "grounded_rate": 0.0,
        "error_rate": 0.0,
    }
