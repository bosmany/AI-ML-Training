"""Pick which implementation the tests import as ``lab``.

Learners run ``pytest`` (target = starter). Maintainers/CI run ``LAB_TARGET=solution pytest``.
Everything here is hermetic: chromadb is a real local library writing to ``tmp_path``,
and TfidfEmbedder is a real local sklearn pipeline - no network, no account, no server.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True

_TARGET = os.environ.get("LAB_TARGET", "starter")
_LAB_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_LAB_DIR / _TARGET))

import pytest  # noqa: E402


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "live: needs a real API key/account (e.g. EMBEDDING_API_KEY); "
        "excluded by default, run with `pytest -m live`",
    )


@pytest.fixture
def store_dir(tmp_path) -> str:
    """A fresh, per-test directory for chromadb's persisted sqlite files."""
    return str(tmp_path / "chroma")


# A small, fixed "Acme Widgets API" support knowledge base, deliberately written so each
# document uses distinct vocabulary - this keeps TF-IDF retrieval deterministic and lets
# tests assert *which* document should win for a given query without ambiguity.
KNOWLEDGE_BASE = [
    {
        "id": "auth",
        "text": (
            "Authentication: every request to the Acme Widgets API must include an "
            "Authorization header with a Bearer API key. Keys are created in the "
            "dashboard under Settings > API Keys and can be rotated at any time."
        ),
        "metadata": {"topic": "authentication"},
    },
    {
        "id": "rate-limits",
        "text": (
            "Rate limits: the API allows 100 requests per minute per API key. "
            "Exceeding the limit returns HTTP 429 with a Retry-After header telling "
            "you how many seconds to wait before sending the next request."
        ),
        "metadata": {"topic": "rate-limiting"},
    },
    {
        "id": "refunds",
        "text": (
            "Refunds and billing: a completed order can be refunded within 30 days "
            "by calling POST /orders/{id}/refund. Partial refunds are supported by "
            "passing an amount; the customer's card is credited within 5 business days."
        ),
        "metadata": {"topic": "billing"},
    },
    {
        "id": "webhooks",
        "text": (
            "Webhooks: subscribe to order.created, order.refunded and widget.shipped "
            "events by registering an HTTPS endpoint. Each delivery includes an "
            "X-Acme-Signature header so you can verify the payload came from Acme."
        ),
        "metadata": {"topic": "webhooks"},
    },
    {
        "id": "pagination",
        "text": (
            "Pagination: list endpoints such as GET /widgets accept a limit and a "
            "cursor query parameter. The response includes a next_cursor field; pass "
            "it back as cursor to fetch the following page until next_cursor is null."
        ),
        "metadata": {"topic": "pagination"},
    },
    {
        "id": "errors",
        "text": (
            "Error codes: the API returns a JSON body with an error.code and "
            "error.message on any 4xx or 5xx response, such as invalid_request, "
            "not_found, or rate_limited, so clients can branch on a stable string."
        ),
        "metadata": {"topic": "errors"},
    },
]


@pytest.fixture
def knowledge_base() -> list[dict]:
    return [dict(doc) for doc in KNOWLEDGE_BASE]


@pytest.fixture
def corpus_texts(knowledge_base) -> list[str]:
    return [doc["text"] for doc in knowledge_base]
