"""A real, local, offline embedding approach: no API key, no account, no network.

Ch35 taught TF-IDF + cosine similarity as the RagChatbot's retrieval math. This module
is the exact same idea, packaged as a reusable ``Embedder`` (``fit`` once on a corpus,
``embed`` any text into a vector) so it can feed a real vector database instead of a
Python list.

Honest tradeoff (see the lab README's "Quality tradeoff" section for the full story):
TF-IDF is a *lexical* representation - it scores word overlap, not meaning. "How do I
get my money back" will NOT match a document that only ever says "refund policy" unless
the vectoriser happens to share a token. A real sentence-embedding model (or a hosted
embeddings API - see ``hosted_embedding.HostedEmbedder``) captures semantic similarity;
TF-IDF does not. It is still a completely real, non-fake local embedding: real vectors,
real cosine geometry, real ranking - just a cruder one, and one that needs nothing but
the sklearn already installed in this venv.
"""

from __future__ import annotations

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer


class TfidfEmbedder:
    """Fits a TF-IDF vocabulary on a corpus, then embeds any text against it.

    Vectors are L2-normalised, so a plain dot product between two embeddings equals
    their cosine similarity - which is exactly what ``ChromaVectorStore`` (configured
    with ``hnsw:space: cosine``) expects.
    """

    def __init__(self, max_features: int = 4096) -> None:
        self.max_features = max_features
        # stop_words="english" matches Ch35's remove_stop() step: common words like
        # "the"/"is"/"what" appear in nearly every document, so without removing them
        # an unrelated query can still share enough of them to look falsely "grounded".
        self._vectorizer = TfidfVectorizer(max_features=max_features, norm="l2", stop_words="english")
        self._fitted = False
        self.dim = 0

    @property
    def fitted(self) -> bool:
        return self._fitted

    def fit(self, corpus: list[str]) -> None:
        """Build the TF-IDF vocabulary from ``corpus``. Must be called before ``embed``."""
        if not corpus:
            raise ValueError("cannot fit an embedder on an empty corpus")
        matrix = self._vectorizer.fit_transform(corpus)
        self.dim = matrix.shape[1]
        self._fitted = True

    def embed(self, texts: list[str]) -> np.ndarray:
        """Return an (len(texts), self.dim) array of L2-normalised TF-IDF vectors.

        Words never seen during ``fit`` are silently dropped (out-of-vocabulary), the
        same limitation any fixed-vocabulary local embedder has without a retrain.
        """
        if not self._fitted:
            raise RuntimeError("call fit() before embed()")
        if not texts:
            return np.zeros((0, self.dim), dtype=np.float64)
        matrix = self._vectorizer.transform(texts).toarray().astype(np.float64)
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return matrix / norms
