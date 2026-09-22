"""RagChatbot: Ch35's retrieve -> prompt -> (simulated) generate -> monitor pattern,
now backed by a real embedder and a real local vector database instead of an
in-memory list and a hand-rolled cosine loop.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from .vectorstore import ChromaVectorStore, RetrievedDocument

# Same cutoff Ch35 used: below this top-hit similarity, treat the answer as ungrounded
# rather than let the (simulated) generator hallucinate from irrelevant context.
SIM_THRESHOLD = 0.05


class Embedder(Protocol):
    def fit(self, corpus: list[str]) -> None: ...
    def embed(self, texts: list[str]): ...


def build_prompt(query: str, retrieved: list[RetrievedDocument]) -> str:
    """Build the exact prompt a real LLM would receive - unchanged from Ch35's pattern."""
    if not retrieved:
        context = "(no relevant context found)"
    else:
        context = "\n\n".join(f"[{doc.id}] {doc.text}" for doc in retrieved)
    return (
        "Answer the question using ONLY the context below. "
        "If the context does not contain the answer, say you don't know.\n\n"
        f"Context:\n{context}\n\nQuestion: {query}\nAnswer:"
    )


@dataclass
class HealthMonitor:
    """Ch35's health monitor, reused verbatim: count requests, grounded vs. not, errors."""

    requests: int = 0
    grounded_responses: int = 0
    ungrounded_responses: int = 0
    errors: int = 0

    def log_request(self, grounded: bool, is_error: bool = False) -> None:
        self.requests += 1
        if is_error:
            self.errors += 1
        elif grounded:
            self.grounded_responses += 1
        else:
            self.ungrounded_responses += 1

    def report(self) -> dict[str, Any]:
        total = self.requests or 1
        return {
            "requests": self.requests,
            "grounded_responses": self.grounded_responses,
            "ungrounded_responses": self.ungrounded_responses,
            "errors": self.errors,
            "grounded_rate": self.grounded_responses / total,
            "error_rate": self.errors / total,
        }


class RagChatbot:
    """Same public shape as Ch35's ``RagChatbot``, extended with real infra underneath.

    - ``load_documents`` fits the embedder on the corpus and upserts it into a real
      chromadb collection persisted at ``persist_directory``.
    - ``retrieve`` embeds the query and asks the vector store for nearest neighbours.
    - ``chat`` applies Ch35's exact grounding rule (``similarity < SIM_THRESHOLD`` ->
      not grounded) and logs every call through ``HealthMonitor``.
    """

    SIM_THRESHOLD = SIM_THRESHOLD

    def __init__(self, persist_directory: str, collection_name: str = "knowledge_base", embedder: Embedder | None = None) -> None:
        from .embeddings import TfidfEmbedder  # local default; avoids a hard import cycle

        self.embedder: Embedder = embedder or TfidfEmbedder()
        self.store = ChromaVectorStore(persist_directory, collection_name)
        self.monitor = HealthMonitor()
        self._loaded = False

    def load_documents(self, docs: list[dict[str, Any]]) -> None:
        """``docs``: a list of ``{"id": str, "text": str, "metadata": dict}`` (metadata optional).

        TODO:
        - raise ValueError if docs is empty
        - pull out ids, texts, and metadatas (default {} per doc when missing)
        - self.embedder.fit(texts), then embeddings = self.embedder.embed(texts)
        - self.store.upsert(ids=..., texts=..., embeddings=..., metadatas=...)
        - set self._loaded = True
        """
        raise NotImplementedError

    def retrieve(self, query: str, top_k: int = 3) -> list[RetrievedDocument]:
        """TODO:
        - raise RuntimeError if load_documents() has not been called yet
        - embed [query] (a single-element list), unpack the one embedding
        - return self.store.query(query_embedding, top_k=top_k)
        """
        raise NotImplementedError

    def chat(self, query: str, top_k: int = 3) -> dict[str, Any]:
        """Retrieve, decide groundedness, build the prompt, and (simulate) an answer.

        Returns ``{"answer", "similarity", "grounded", "sources", "prompt"}`` - same
        keys Ch35's RagChatbot returned, plus ``prompt`` and ``sources`` for the
        real multi-document case a single in-memory list didn't need to expose.

        TODO:
        - raise RuntimeError if load_documents() has not been called yet
        - if query is empty/whitespace: log_request(grounded=False, is_error=True),
          then raise ValueError
        - retrieved = self.retrieve(query, top_k=top_k)
        - top_similarity = retrieved[0].similarity if retrieved else 0.0
        - grounded = bool(retrieved) and top_similarity >= self.SIM_THRESHOLD
        - build the prompt from retrieved docs only when grounded (empty list otherwise)
        - answer: "Based on {top id}: {top text}" when grounded, else the
          "I don't know - nothing in the knowledge base is relevant enough..." message
        - self.monitor.log_request(grounded=grounded)
        - return the dict described above, with sources = [] when not grounded
        """
        raise NotImplementedError

    def health_report(self) -> dict[str, Any]:
        return self.monitor.report()
