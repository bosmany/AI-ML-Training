"""A real local vector database: chromadb, persisted to disk, no server and no account.

The store never asks chromadb to compute embeddings itself (that would require
chromadb's default embedding function, which downloads an ONNX model over the network
the first time it runs). Every collection is created with ``embedding_function=None``
and every call passes precomputed embeddings explicitly - so this module never touches
the network, whichever ``Embedder`` produced those vectors.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

import chromadb
from chromadb.config import Settings


@dataclass
class RetrievedDocument:
    """One hit returned by :meth:`ChromaVectorStore.query`."""

    id: str
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)
    similarity: float = 0.0  # cosine similarity, roughly [-1, 1]; higher = more relevant


class ChromaVectorStore:
    """Thin, typed wrapper around one real local chromadb collection."""

    def __init__(self, persist_directory: str, collection_name: str = "knowledge_base") -> None:
        self._client = chromadb.PersistentClient(
            path=persist_directory,
            settings=Settings(anonymized_telemetry=False, allow_reset=True),
        )
        self._collection = self._client.get_or_create_collection(
            name=collection_name,
            embedding_function=None,
            metadata={"hnsw:space": "cosine"},
        )

    def count(self) -> int:
        return self._collection.count()

    def upsert(
        self,
        ids: Iterable[str],
        texts: Iterable[str],
        embeddings: Any,
        metadatas: Iterable[dict[str, Any]] | None = None,
    ) -> None:
        """Insert or update documents by id. Re-using an existing id replaces it in place."""
        ids = list(ids)
        texts = list(texts)
        embeddings = [list(map(float, vec)) for vec in embeddings]
        if not (len(ids) == len(texts) == len(embeddings)):
            raise ValueError("ids, texts and embeddings must all have the same length")
        if not ids:
            raise ValueError("upsert requires at least one document")
        metadatas = list(metadatas) if metadatas is not None else [None for _ in ids]
        if len(metadatas) != len(ids):
            raise ValueError("metadatas must have the same length as ids")
        # chromadb rejects an empty dict ({}) as metadata (it wants a non-empty dict or
        # None) - normalise "no metadata" to None so callers can pass {} freely.
        metadatas = [meta or None for meta in metadatas]
        self._collection.upsert(ids=ids, documents=texts, embeddings=embeddings, metadatas=metadatas)

    def query(self, query_embedding: Any, top_k: int = 3) -> list[RetrievedDocument]:
        """Return up to ``top_k`` nearest documents, most similar first."""
        if top_k <= 0:
            raise ValueError("top_k must be >= 1")
        available = self._collection.count()
        if available == 0:
            return []
        result = self._collection.query(
            query_embeddings=[list(map(float, query_embedding))],
            n_results=min(top_k, available),
        )
        out: list[RetrievedDocument] = []
        for doc_id, text, meta, distance in zip(
            result["ids"][0], result["documents"][0], result["metadatas"][0], result["distances"][0]
        ):
            # chromadb's cosine "distance" is (1 - cosine_similarity); undo that to get
            # back a similarity score the rest of the lab reasons about directly.
            out.append(RetrievedDocument(id=doc_id, text=text, metadata=meta or {}, similarity=1.0 - distance))
        return out

    def delete(self, ids: Iterable[str]) -> None:
        self._collection.delete(ids=list(ids))

    def reset(self) -> None:
        """Drop every document. Mainly useful for tests."""
        self._client.reset()
