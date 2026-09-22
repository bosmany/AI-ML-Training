"""Hugging Face Spaces app: the same TF-IDF + chromadb RAG pattern from this lab,
wrapped in a small Gradio UI so it can be pushed to a free HF Space and get a public URL.

This file is self-contained on purpose (it does not import the `lab` package) so the
whole Space is just this file + requirements.txt - the two things you actually push.

*** This app has never been deployed from this sandbox: there is no Hugging Face
account or token here. See the lab README, "Deploying to Hugging Face Spaces", for the
exact manual steps to push it and get a real public URL. Nothing in this file's
docstrings or comments should be read as a claim that it is already live. ***

Offline by default: retrieval uses the same TF-IDF + chromadb approach as the rest of
this lab, so the Space works the moment it starts, with zero secrets. If the Space
owner adds an `EMBEDDING_API_KEY` repository secret (Settings > Variables and secrets),
the app swaps in real hosted embeddings for better (semantic, not just lexical) answers -
see `_build_embedder()` below.
"""

from __future__ import annotations

import os
import uuid

import chromadb
import gradio as gr
import numpy as np
import requests
from chromadb.config import Settings
from sklearn.feature_extraction.text import TfidfVectorizer

SIM_THRESHOLD = 0.05

KNOWLEDGE_BASE = [
    {
        "id": "auth",
        "text": (
            "Authentication: every request to the Acme Widgets API must include an "
            "Authorization header with a Bearer API key, created in the dashboard "
            "under Settings > API Keys."
        ),
    },
    {
        "id": "rate-limits",
        "text": (
            "Rate limits: the API allows 100 requests per minute per API key. "
            "Exceeding it returns HTTP 429 with a Retry-After header."
        ),
    },
    {
        "id": "refunds",
        "text": (
            "Refunds and billing: a completed order can be refunded within 30 days via "
            "POST /orders/{id}/refund. Partial refunds are supported; the card is "
            "credited within 5 business days."
        ),
    },
    {
        "id": "webhooks",
        "text": (
            "Webhooks: subscribe to order.created, order.refunded and widget.shipped "
            "events. Each delivery includes an X-Acme-Signature header to verify it "
            "came from Acme."
        ),
    },
    {
        "id": "pagination",
        "text": (
            "Pagination: list endpoints accept a limit and a cursor parameter. The "
            "response includes next_cursor; pass it back as cursor for the next page."
        ),
    },
    {
        "id": "errors",
        "text": (
            "Error codes: responses include an error.code and error.message such as "
            "invalid_request, not_found, or rate_limited on any 4xx/5xx response."
        ),
    },
]


class _TfidfEmbedder:
    """Offline fallback: no key, no account, no network - real vectors, lexical only."""

    def __init__(self) -> None:
        self._vectorizer = TfidfVectorizer(norm="l2", stop_words="english")
        self._fitted = False

    def fit(self, corpus: list[str]) -> None:
        self._vectorizer.fit(corpus)
        self._fitted = True

    def embed(self, texts: list[str]) -> np.ndarray:
        matrix = self._vectorizer.transform(texts).toarray().astype(np.float64)
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return matrix / norms


class _HostedEmbedder:
    """Optional real hosted embeddings, used only when EMBEDDING_API_KEY is set as a
    Space secret. Real semantic similarity instead of TF-IDF's word-overlap heuristic."""

    def __init__(self, api_key: str, base_url: str = "https://api.openai.com/v1", model: str = "text-embedding-3-small") -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model

    def fit(self, corpus: list[str]) -> None:  # pretrained model, nothing to fit
        return None

    def embed(self, texts: list[str]) -> np.ndarray:
        response = requests.post(
            f"{self.base_url}/embeddings",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={"model": self.model, "input": texts},
            timeout=30.0,
        )
        response.raise_for_status()
        vectors = np.array([row["embedding"] for row in response.json()["data"]], dtype=np.float64)
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return vectors / norms


def _build_embedder():
    api_key = os.environ.get("EMBEDDING_API_KEY")
    if api_key:
        return _HostedEmbedder(api_key=api_key), "hosted embeddings API (EMBEDDING_API_KEY set)"
    return _TfidfEmbedder(), "local TF-IDF (offline, no key configured)"


def _build_index():
    embedder, mode = _build_embedder()
    texts = [doc["text"] for doc in KNOWLEDGE_BASE]
    embedder.fit(texts)
    vectors = embedder.embed(texts)

    client = chromadb.PersistentClient(
        path=f"/tmp/rag-space-{uuid.uuid4().hex}",
        settings=Settings(anonymized_telemetry=False, allow_reset=True),
    )
    collection = client.create_collection(
        name="knowledge_base",
        embedding_function=None,
        metadata={"hnsw:space": "cosine"},
    )
    collection.upsert(
        ids=[doc["id"] for doc in KNOWLEDGE_BASE],
        documents=texts,
        embeddings=[vec.tolist() for vec in vectors],
    )
    return embedder, collection, mode


_EMBEDDER, _COLLECTION, _MODE = _build_index()


def answer_question(query: str) -> str:
    if not query or not query.strip():
        return "Please type a question about the Acme Widgets API."

    [query_vector] = _EMBEDDER.embed([query])
    result = _COLLECTION.query(query_embeddings=[query_vector.tolist()], n_results=1)
    if not result["ids"][0]:
        similarity = 0.0
        doc_id, doc_text = None, None
    else:
        doc_id = result["ids"][0][0]
        doc_text = result["documents"][0][0]
        similarity = 1.0 - result["distances"][0][0]

    grounded = doc_id is not None and similarity >= SIM_THRESHOLD
    if grounded:
        return f"[grounded, similarity={similarity:.3f}, source={doc_id}]\n\n{doc_text}"
    return (
        f"[not grounded, similarity={similarity:.3f}]\n\n"
        "I don't know - nothing in the knowledge base is relevant enough to that question."
    )


demo = gr.Interface(
    fn=answer_question,
    inputs=gr.Textbox(label="Ask about the Acme Widgets API", placeholder="How do refunds work?"),
    outputs=gr.Textbox(label="Answer"),
    title="RAG over a real local vector DB (chromadb)",
    description=(
        f"Retrieval mode: **{_MODE}**. Real chromadb collection, real embeddings, "
        "real cosine similarity - the same pattern taught in this course's labs, "
        "running live in this Space. Set an `EMBEDDING_API_KEY` repo secret to swap "
        "in real hosted embeddings instead of the offline TF-IDF fallback."
    ),
    examples=[
        "How do I authenticate my API requests?",
        "What happens if I exceed the rate limit?",
        "How long do refunds take to show up?",
        "What is the capital of France?",  # deliberately out of scope: should be ungrounded
    ],
)

if __name__ == "__main__":
    demo.launch()
