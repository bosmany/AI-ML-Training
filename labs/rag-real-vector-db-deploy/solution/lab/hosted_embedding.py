"""Optional: swap the offline TF-IDF embedder for a real hosted embeddings API.

This is the "higher quality, needs an account" path the lab README documents next to
the offline one. It is a real, working client for any OpenAI-compatible
``POST {base_url}/embeddings`` endpoint (OpenAI itself, or a compatible provider) -
NOT a mock. It is gated exactly like lab 5's live LLM tests: it raises immediately if
no API key is configured, and it is only ever exercised by ``tests/test_live_hosted_embedding.py``,
marked ``@pytest.mark.live`` and skipped unless ``EMBEDDING_API_KEY`` is set in the
environment. ``LAB_TARGET=solution pytest`` (the graded, offline run) never calls the
network through this class.
"""

from __future__ import annotations

import os

import numpy as np
import requests


class HostedEmbedder:
    """Real hosted embeddings client. Needs ``EMBEDDING_API_KEY`` (or ``api_key=``).

    Same ``fit``/``embed`` shape as :class:`lab.embeddings.TfidfEmbedder`, so it is a
    drop-in replacement: ``RagChatbot(persist_directory, embedder=HostedEmbedder())``.
    Unlike TF-IDF, there is nothing to "fit" locally - the model was pre-trained by the
    provider - so ``fit`` is a no-op kept only to satisfy the ``Embedder`` protocol.
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = "https://api.openai.com/v1",
        model: str = "text-embedding-3-small",
        timeout: float = 30.0,
    ) -> None:
        self.api_key = api_key or os.environ.get("EMBEDDING_API_KEY")
        if not self.api_key:
            raise RuntimeError(
                "HostedEmbedder needs a real API key: set EMBEDDING_API_KEY or pass "
                "api_key=... . See the lab README, 'Swapping in a real embedding API'."
            )
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.dim: int | None = None

    def fit(self, corpus: list[str]) -> None:  # noqa: ARG002 - protocol compatibility
        return None

    def embed(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, self.dim or 0), dtype=np.float64)
        response = requests.post(
            f"{self.base_url}/embeddings",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={"model": self.model, "input": texts},
            timeout=self.timeout,
        )
        response.raise_for_status()
        rows = response.json()["data"]
        vectors = np.array([row["embedding"] for row in rows], dtype=np.float64)
        self.dim = vectors.shape[1]
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return vectors / norms
