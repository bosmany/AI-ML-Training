"""HostedEmbedder: the optional real hosted-embedding-API path.

These are the only assertions about HostedEmbedder that run in the graded, offline
suite - they never make a network call. The actual "call a real embeddings API" path
lives in test_live_hosted_embedding.py, marked @pytest.mark.live and skipped unless a
real key is configured (see README).
"""

from __future__ import annotations

import pytest

from lab import HostedEmbedder


def test_missing_api_key_raises_immediately(monkeypatch) -> None:
    monkeypatch.delenv("EMBEDDING_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="EMBEDDING_API_KEY"):
        HostedEmbedder()


def test_explicit_api_key_is_accepted_without_a_network_call(monkeypatch) -> None:
    monkeypatch.delenv("EMBEDDING_API_KEY", raising=False)
    embedder = HostedEmbedder(api_key="sk-fake-key-never-sent-anywhere-in-this-test")
    assert embedder.api_key == "sk-fake-key-never-sent-anywhere-in-this-test"


def test_env_var_api_key_is_picked_up(monkeypatch) -> None:
    monkeypatch.setenv("EMBEDDING_API_KEY", "sk-from-env")
    embedder = HostedEmbedder()
    assert embedder.api_key == "sk-from-env"


def test_fit_is_a_no_op(monkeypatch) -> None:
    monkeypatch.setenv("EMBEDDING_API_KEY", "sk-from-env")
    embedder = HostedEmbedder()
    assert embedder.fit(["some", "corpus"]) is None


def test_embed_empty_list_needs_no_network_call(monkeypatch) -> None:
    monkeypatch.setenv("EMBEDDING_API_KEY", "sk-from-env")
    embedder = HostedEmbedder()
    result = embedder.embed([])
    assert result.shape == (0, 0)
