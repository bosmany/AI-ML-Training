"""Input parsing/validation and money formatting. Money is integer cents everywhere - never a float."""
from __future__ import annotations

from datetime import date

from .errors import ValidationError  # noqa: F401  (you will raise it)


def parse_amount(text: str) -> int:
    """Parse ``"12.50"`` into integer cents (``1250``).

    TODO:
    - strip surrounding whitespace; accept only digits with an optional ``.`` and 1-2 decimals
      (``"12"``, ``"12.5"``, ``"0.10"``). Reject ``""``, ``"abc"``, ``"1e2"``, ``"nan"``, ``"1,50"``,
      ``"12."``, ``".5"`` and anything with 3+ decimals (do not silently round).
    - reject zero and negative amounts. Every rejection raises ``ValidationError`` with a clear message.
    - never use ``float``: ``Decimal(text) * 100`` (or split on ``.``) gives exact cents.
    """
    raise NotImplementedError


def format_cents(cents: int) -> str:
    """``1250`` -> ``"12.50"``, ``5`` -> ``"0.05"``, ``0`` -> ``"0.00"``.

    TODO: use ``divmod(cents, 100)`` - no float division.
    """
    raise NotImplementedError


def parse_date(text: str) -> date:
    """Strict ``YYYY-MM-DD`` that must be a real calendar date.

    TODO:
    - reject ``20250301`` and ``2025-3-1`` (``date.fromisoformat`` is too lenient on 3.11+: check the shape yourself)
    - reject ``2025-02-30`` / ``2025-13-01`` / ``2023-02-29``; accept ``2024-02-29``
    - raise ``ValidationError`` (not ``ValueError``)
    """
    raise NotImplementedError


def parse_month(text: str) -> tuple[int, int]:
    """``"2025-03"`` -> ``(2025, 3)``.

    TODO: shape ``YYYY-MM`` with month 01-12, else ``ValidationError``.
    """
    raise NotImplementedError


def normalize_category(text: str) -> str:
    """Strip and lowercase; afterwards only ``a-z``, ``0-9``, ``_`` and ``-`` are allowed (non-empty).

    TODO: ``" Food "`` -> ``"food"``; ``""``, ``"two words"``, ``"a/b"`` -> ``ValidationError``.
    """
    raise NotImplementedError
