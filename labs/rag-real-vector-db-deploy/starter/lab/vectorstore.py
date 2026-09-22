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
        """Insert or update documents by id. Re-using an existing id replaces it in place.

        TODO:
        - materialise ids/texts/embeddings into lists; convert every embedding's values
          to float
        - raise ValueError if ids, texts and embeddings don't all have the same length,
          or if ids is empty
        - default metadatas to a list of Nones when None, else raise ValueError if its
          length does not match ids
        - chromadb rejects an empty dict ({}) as metadata (it wants a non-empty dict or
          None) - normalise any falsy metadata entry to None before calling chromadb
        - call self._collection.upsert(ids=..., documents=..., embeddings=..., metadatas=...)
        """
        raise NotImplementedError

    def query(self, query_embedding: Any, top_k: int = 3) -> list[RetrievedDocument]:
        """Return up to ``top_k`` nearest documents, most similar first.

        TODO:
        - raise ValueError if top_k < 1
        - return [] if the collection is empty (self.count() == 0)
        - call self._collection.query(query_embeddings=[...], n_results=min(top_k, count))
        - chromadb returns cosine *distance* (1 - cosine_similarity); convert each
          result back to a RetrievedDocument with similarity = 1.0 - distance
        """
        raise NotImplementedError

    def delete(self, ids: Iterable[str]) -> None:
        self._collection.delete(ids=list(ids))

    def reset(self) -> None:
        """Drop every document. Mainly useful for tests."""
        self._client.reset()
