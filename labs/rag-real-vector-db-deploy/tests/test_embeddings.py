"""TfidfEmbedder: a real, local, offline embedding pipeline (no API key, no network)."""

from __future__ import annotations

import numpy as np
import pytest

from lab import TfidfEmbedder


def test_fit_on_empty_corpus_raises() -> None:
    embedder = TfidfEmbedder()
    with pytest.raises(ValueError):
        embedder.fit([])


def test_embed_before_fit_raises() -> None:
    embedder = TfidfEmbedder()
    with pytest.raises(RuntimeError, match="fit"):
        embedder.embed(["hello"])


def test_fit_sets_fitted_flag_and_dimension(corpus_texts) -> None:
    embedder = TfidfEmbedder()
    assert embedder.fitted is False
    embedder.fit(corpus_texts)
    assert embedder.fitted is True
    assert embedder.dim > 0


def test_embed_returns_matrix_of_expected_shape(corpus_texts) -> None:
    embedder = TfidfEmbedder()
    embedder.fit(corpus_texts)
    vectors = embedder.embed(corpus_texts)
    assert vectors.shape == (len(corpus_texts), embedder.dim)


def test_embed_empty_list_returns_zero_rows(corpus_texts) -> None:
    embedder = TfidfEmbedder()
    embedder.fit(corpus_texts)
    vectors = embedder.embed([])
    assert vectors.shape == (0, embedder.dim)


def test_vectors_are_l2_normalised(corpus_texts) -> None:
    embedder = TfidfEmbedder()
    embedder.fit(corpus_texts)
    vectors = embedder.embed(corpus_texts)
    norms = np.linalg.norm(vectors, axis=1)
    for norm in norms:
        assert norm == pytest.approx(1.0, abs=1e-6)


def test_embedding_is_deterministic(corpus_texts) -> None:
    embedder = TfidfEmbedder()
    embedder.fit(corpus_texts)
    first = embedder.embed(["how do I authenticate my requests?"])
    second = embedder.embed(["how do I authenticate my requests?"])
    assert np.allclose(first, second)


def test_similar_text_scores_higher_than_unrelated_text(corpus_texts) -> None:
    embedder = TfidfEmbedder()
    embedder.fit(corpus_texts)
    auth_doc = corpus_texts[0]  # the authentication document
    query_vec = embedder.embed(["How do I authenticate my API requests with a key?"])[0]
    same_topic_vec = embedder.embed([auth_doc])[0]
    unrelated_vec = embedder.embed(["What is the capital city of France?"])[0]

    sim_same_topic = float(np.dot(query_vec, same_topic_vec))
    sim_unrelated = float(np.dot(query_vec, unrelated_vec))
    assert sim_same_topic > sim_unrelated


def test_out_of_vocabulary_query_does_not_crash(corpus_texts) -> None:
    embedder = TfidfEmbedder()
    embedder.fit(corpus_texts)
    # None of these words appear anywhere in the fitted corpus.
    vector = embedder.embed(["zzyzx quixotic marmalade nebula"])
    assert vector.shape == (1, embedder.dim)


def test_two_embedders_fit_on_same_corpus_agree(corpus_texts) -> None:
    a = TfidfEmbedder()
    b = TfidfEmbedder()
    a.fit(corpus_texts)
    b.fit(corpus_texts)
    assert np.allclose(a.embed(corpus_texts), b.embed(corpus_texts))


def test_max_features_is_respected() -> None:
    corpus = ["alpha beta gamma delta epsilon zeta eta theta iota kappa"] * 3
    embedder = TfidfEmbedder(max_features=3)
    embedder.fit(corpus)
    assert embedder.dim <= 3
