"""Real local vector DB + real (offline) embeddings, extending Ch35's RagChatbot.

Public API:
    TfidfEmbedder    - offline, no-API-key embedder (Ch35's TF-IDF pipeline, vectorised)
    HostedEmbedder   - optional real hosted embedding API (needs a key; gated, see README)
    RetrievedDocument - one hit returned by the vector store
    ChromaVectorStore - thin wrapper around a real local chromadb collection
    RagChatbot       - ties embedder + vector store + Ch35's grounding logic together
    build_prompt     - Ch35's prompt-construction helper, unchanged
    SIM_THRESHOLD    - Ch35's "not grounded" cutoff (0.05), reused for continuity
"""

from .embeddings import TfidfEmbedder
from .hosted_embedding import HostedEmbedder
from .rag import RagChatbot, SIM_THRESHOLD, HealthMonitor, build_prompt
from .vectorstore import ChromaVectorStore, RetrievedDocument

__all__ = [
    "TfidfEmbedder",
    "HostedEmbedder",
    "RagChatbot",
    "SIM_THRESHOLD",
    "HealthMonitor",
    "build_prompt",
    "ChromaVectorStore",
    "RetrievedDocument",
]
