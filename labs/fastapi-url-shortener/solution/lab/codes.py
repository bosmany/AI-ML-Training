"""Short-code generation and validation (reference solution)."""

from __future__ import annotations

import re
import secrets
import string

from lab.errors import ValidationFailed

ALPHABET = string.digits + string.ascii_uppercase + string.ascii_lowercase  # base62
CODE_LENGTH = 7
RESERVED_CODES = frozenset({"docs", "redoc", "openapi.json", "links"})
CUSTOM_CODE_RE = re.compile(r"[A-Za-z0-9_-]{3,32}")


def generate_code(length: int = CODE_LENGTH) -> str:
    """A random base62 code of exactly ``length`` characters (cryptographically random)."""
    return "".join(secrets.choice(ALPHABET) for _ in range(length))


def validate_custom_code(code: str) -> str:
    """Return ``code`` if usable, else raise :class:`ValidationFailed`."""
    if code.casefold() in RESERVED_CODES:
        raise ValidationFailed(f"'{code}' is a reserved word and cannot be used as a code")
    if not CUSTOM_CODE_RE.fullmatch(code):
        raise ValidationFailed("custom_code must be 3-32 characters of letters, digits, '-' or '_'")
    return code
