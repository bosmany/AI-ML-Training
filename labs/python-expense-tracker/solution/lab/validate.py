"""Input parsing/validation and money formatting. Money is integer cents everywhere - never a float."""
from __future__ import annotations

import re
from datetime import date
from decimal import Decimal

from .errors import ValidationError

_AMOUNT_RE = re.compile(r"[0-9]+(?:\.[0-9]{1,2})?")
_DATE_RE = re.compile(r"([0-9]{4})-([0-9]{2})-([0-9]{2})")
_MONTH_RE = re.compile(r"([0-9]{4})-(0[1-9]|1[0-2])")
_CATEGORY_RE = re.compile(r"[a-z0-9_-]+")


def parse_amount(text: str) -> int:
    """Parse ``"12.50"`` into integer cents (``1250``)."""
    cleaned = text.strip()
    if cleaned.startswith("-"):
        raise ValidationError(f"invalid amount {text!r}: amount must be positive")
    if not _AMOUNT_RE.fullmatch(cleaned):
        raise ValidationError(f"invalid amount {text!r}: use a number with at most 2 decimals, e.g. 12.50")
    cents = int(Decimal(cleaned) * 100)  # exact: at most 2 decimals
    if cents <= 0:
        raise ValidationError(f"invalid amount {text!r}: amount must be greater than zero")
    return cents


def format_cents(cents: int) -> str:
    """``1250`` -> ``"12.50"``, ``5`` -> ``"0.05"``."""
    sign = "-" if cents < 0 else ""
    whole, frac = divmod(abs(cents), 100)
    return f"{sign}{whole}.{frac:02d}"


def parse_date(text: str) -> date:
    """Strict ``YYYY-MM-DD`` (no ``20250301``, no ``2025-3-1``) that must be a real calendar date."""
    m = _DATE_RE.fullmatch(text.strip())
    if not m:
        raise ValidationError(f"invalid date {text!r}: use YYYY-MM-DD")
    try:
        return date(int(m[1]), int(m[2]), int(m[3]))
    except ValueError:
        raise ValidationError(f"invalid date {text!r}: not a real calendar date") from None


def parse_month(text: str) -> tuple[int, int]:
    """``"2025-03"`` -> ``(2025, 3)``."""
    m = _MONTH_RE.fullmatch(text.strip())
    if not m:
        raise ValidationError(f"invalid month {text!r}: use YYYY-MM")
    return int(m[1]), int(m[2])


def normalize_category(text: str) -> str:
    """Strip + lowercase; only ``a-z 0-9 _ -`` are allowed afterwards."""
    cleaned = text.strip().lower()
    if not _CATEGORY_RE.fullmatch(cleaned):
        raise ValidationError(f"invalid category {text!r}: use letters, digits, '-' or '_'")
    return cleaned
