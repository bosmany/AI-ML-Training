"""ChromaVectorStore: a real local chromadb collection, persisted under tmp_path."""

from __future__ import annotations

import pytest

from lab import ChromaVectorStore, TfidfEmbedder


def _embed_all(corpus_texts):
    embedder = TfidfEmbedder()
    embedder.fit(corpus_texts)
    return embedder, embedder.embed(corpus_texts)


def test_upsert_then_query_returns_best_match(store_dir, knowledge_base, corpus_texts) -> None:
    store = ChromaVectorStore(store_dir)
    assert store.count() == 0  # a freshly created collection starts empty
    embedder, vectors = _embed_all(corpus_texts)
    ids = [doc["id"] for doc in knowledge_base]
    metadatas = [doc["metadata"] for doc in knowledge_base]
    store.upsert(ids=ids, texts=corpus_texts, embeddings=vectors, metadatas=metadatas)

    query_vec = embedder.embed(["What header carries my API key for authentication?"])[0]
    results = store.query(query_vec, top_k=1)

    assert len(results) == 1
    assert results[0].id == "auth"
    assert results[0].metadata["topic"] == "authentication"


def test_upsert_mismatched_lengths_raises(store_dir) -> None:
    store = ChromaVectorStore(store_dir)
    with pytest.raises(ValueError):
        store.upsert(ids=["a", "b"], texts=["only one"], embeddings=[[1.0, 0.0]])


def test_upsert_empty_ids_raises(store_dir) -> None:
    store = ChromaVectorStore(store_dir)
    with pytest.raises(ValueError):
        store.upsert(ids=[], texts=[], embeddings=[])


def test_upsert_metadatas_length_mismatch_raises(store_dir) -> None:
    store = ChromaVectorStore(store_dir)
    with pytest.raises(ValueError):
        store.upsert(ids=["a"], texts=["hi"], embeddings=[[1.0, 0.0]], metadatas=[{}, {}])


def test_query_top_k_must_be_positive(store_dir, corpus_texts) -> None:
    store = ChromaVectorStore(store_dir)
    _, vectors = _embed_all(corpus_texts)
    store.upsert(ids=["a"], texts=[corpus_texts[0]], embeddings=[vectors[0]])
    with pytest.raises(ValueError):
        store.query(vectors[0], top_k=0)


def test_query_on_empty_store_returns_empty_list(store_dir, corpus_texts) -> None:
    store = ChromaVectorStore(store_dir)
    _, vectors = _embed_all(corpus_texts)
    assert store.query(vectors[0], top_k=3) == []


def test_query_top_k_larger_than_store_size_does_not_error(store_dir, knowledge_base, corpus_texts) -> None:
    store = ChromaVectorStore(store_dir)
    embedder, vectors = _embed_all(corpus_texts)
    ids = [doc["id"] for doc in knowledge_base][:2]
    store.upsert(ids=ids, texts=corpus_texts[:2], embeddings=vectors[:2])

    results = store.query(vectors[0], top_k=50)
    assert len(results) == 2


def test_results_are_sorted_most_similar_first(store_dir, knowledge_base, corpus_texts) -> None:
    store = ChromaVectorStore(store_dir)
    embedder, vectors = _embed_all(corpus_texts)
    ids = [doc["id"] for doc in knowledge_base]
    store.upsert(ids=ids, texts=corpus_texts, embeddings=vectors)

    query_vec = embedder.embed(["retry after seconds when I exceed 100 requests per minute"])[0]
    results = store.query(query_vec, top_k=len(ids))
    similarities = [doc.similarity for doc in results]
    assert similarities == sorted(similarities, reverse=True)
    assert results[0].id == "rate-limits"


def test_upsert_same_id_replaces_not_duplicates(store_dir, corpus_texts) -> None:
    store = ChromaVectorStore(store_dir)
    embedder, vectors = _embed_all(corpus_texts)
    store.upsert(ids=["doc-1"], texts=[corpus_texts[0]], embeddings=[vectors[0]])
    store.upsert(ids=["doc-1"], texts=["a completely replaced document body"], embeddings=[vectors[1]])

    assert store.count() == 1
    [result] = store.query(vectors[1], top_k=1)
    assert result.text == "a completely replaced document body"


def test_delete_removes_document(store_dir, knowledge_base, corpus_texts) -> None:
    store = ChromaVectorStore(store_dir)
    embedder, vectors = _embed_all(corpus_texts)
    ids = [doc["id"] for doc in knowledge_base]
    store.upsert(ids=ids, texts=corpus_texts, embeddings=vectors)

    store.delete(["auth"])
    assert store.count() == len(ids) - 1
    remaining_ids = {doc.id for doc in store.query(vectors[0], top_k=len(ids))}
    assert "auth" not in remaining_ids


def test_data_persists_across_new_store_instance(store_dir, knowledge_base, corpus_texts) -> None:
    embedder, vectors = _embed_all(corpus_texts)
    ids = [doc["id"] for doc in knowledge_base]
    first = ChromaVectorStore(store_dir)
    first.upsert(ids=ids, texts=corpus_texts, embeddings=vectors)

    reopened = ChromaVectorStore(store_dir)
    assert reopened.count() == len(ids)


def test_reset_clears_the_collection(store_dir, corpus_texts) -> None:
    store = ChromaVectorStore(store_dir)
    embedder, vectors = _embed_all(corpus_texts)
    store.upsert(ids=["a"], texts=[corpus_texts[0]], embeddings=[vectors[0]])
    assert store.count() == 1
    store.reset()
    fresh = ChromaVectorStore(store_dir)
    assert fresh.count() == 0
