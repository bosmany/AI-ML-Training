"""Short-code generation and validation (starter)."""

from __future__ import annotations

import re
import string

from lab.errors import ValidationFailed  # noqa: F401

ALPHABET = string.digits + string.ascii_uppercase + string.ascii_lowercase  # base62 (provided)
CODE_LENGTH = 7
RESERVED_CODES = frozenset({"docs", "redoc", "openapi.json", "links"})
CUSTOM_CODE_RE = re.compile(r"[A-Za-z0-9_-]{3,32}")


def generate_code(length: int = CODE_LENGTH) -> str:
    """A random base62 code of exactly ``length`` characters.

    TODO: build it from ``ALPHABET``. Use the ``secrets`` module (``secrets.choice``), not ``random``:
    guessable codes let people enumerate other users' links.
    """
    raise NotImplementedError("TODO: implement generate_code")


def validate_custom_code(code: str) -> str:
    """Return ``code`` if it may be used as a short code, otherwise raise :class:`ValidationFailed`.

    TODO:
      * reject reserved words (``RESERVED_CODES``) case-insensitively (``str.casefold``) with a message
        that contains the word "reserved" - check this FIRST, ``openapi.json`` would also fail the regex;
      * reject anything that does not ``fullmatch`` ``CUSTOM_CODE_RE``;
      * return the code unchanged (codes are case-sensitive: ``Promo`` and ``promo`` are different).
    """
    raise NotImplementedError("TODO: implement validate_custom_code")
