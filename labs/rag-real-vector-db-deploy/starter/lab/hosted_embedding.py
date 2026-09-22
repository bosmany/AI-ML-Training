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
        """TODO: fail fast without a real credential - a very common production pattern.

        - self.api_key = api_key or the EMBEDDING_API_KEY environment variable
        - if there is still no key, raise RuntimeError with a clear message telling the
          caller to set EMBEDDING_API_KEY or pass api_key=... (never proceed silently
          and only fail later on the first network call)
        - store base_url.rstrip("/"), model, timeout, and self.dim = None
        """
        raise NotImplementedError

    def fit(self, corpus: list[str]) -> None:  # noqa: ARG002 - protocol compatibility
        return None

    def embed(self, texts: list[str]) -> np.ndarray:
        """TODO:
        - return an empty (0, self.dim or 0) array for an empty texts list - no network call
        - otherwise POST to f"{self.base_url}/embeddings" with an Authorization: Bearer
          header and {"model": self.model, "input": texts}, call raise_for_status()
        - parse response.json()["data"], build a float64 array from each row["embedding"],
          record self.dim, L2-normalise every row (guard a zero norm) and return it
        """
        raise NotImplementedError
