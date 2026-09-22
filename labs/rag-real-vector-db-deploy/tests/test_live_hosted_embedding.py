"""Real network test: only runs against a real embeddings API, with a real key.

Excluded by default (see pytest.ini: `addopts = -m "not live"`). Run explicitly with:

    EMBEDDING_API_KEY=sk-... pytest -m live tests/test_live_hosted_embedding.py

Nothing in this file runs, or is claimed to have run, inside this sandbox - there is no
API key here. It exists so a human with a real key (OpenAI, or any OpenAI-compatible
embeddings endpoint) can verify HostedEmbedder for real before relying on it.
"""

from __future__ import annotations

import os

import numpy as np
import pytest

from lab import HostedEmbedder

pytestmark = pytest.mark.live

_HAS_KEY = bool(os.environ.get("EMBEDDING_API_KEY"))


@pytest.mark.skipif(not _HAS_KEY, reason="EMBEDDING_API_KEY is not set - see README for how to get one")
def test_hosted_embedder_returns_real_normalised_vectors() -> None:
    embedder = HostedEmbedder()
    vectors = embedder.embed(["refund policy", "authentication header"])
    assert vectors.shape[0] == 2
    norms = np.linalg.norm(vectors, axis=1)
    assert np.allclose(norms, 1.0, atol=1e-3)


@pytest.mark.skipif(not _HAS_KEY, reason="EMBEDDING_API_KEY is not set - see README for how to get one")
def test_hosted_embedder_captures_semantic_similarity_tfidf_misses() -> None:
    """The whole point of paying for a hosted embedding model: paraphrases with almost
    no shared vocabulary should still score highly similar - unlike TfidfEmbedder."""
    embedder = HostedEmbedder()
    a, b = embedder.embed(["how do I get my money back", "refund policy for orders"])
    similarity = float(np.dot(a, b))
    assert similarity > 0.5
