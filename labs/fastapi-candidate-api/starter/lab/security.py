"""Password hashing and JWT helpers (starter)."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import bcrypt  # noqa: F401
import jwt  # noqa: F401

from lab.errors import AuthenticationError  # noqa: F401
from lab.settings import Settings

BCRYPT_MAX_BYTES = 72


def hash_password(password: str) -> str:
    """Return a salted bcrypt hash (str) of ``password``.

    TODO: encode to UTF-8 first. bcrypt only reads the first 72 BYTES; bcrypt>=5 raises ValueError on
    longer input while older versions silently truncate. Be explicit and consistent: raise
    ``ValueError`` yourself when the encoded password exceeds 72 bytes. Use ``bcrypt.hashpw`` +
    ``bcrypt.gensalt()`` and return the hash decoded to ``str``.
    """
    raise NotImplementedError("TODO: hash_password")


def verify_password(password: str, hashed: str) -> bool:
    """True iff ``password`` matches ``hashed``. Must NEVER raise.

    TODO: return False for a >72-byte candidate (login with a huge password must be a 401, not a 500)
    and for a malformed stored hash (``bcrypt.checkpw`` raises ValueError for those).
    """
    raise NotImplementedError("TODO: verify_password")


def create_access_token(
    user_id: int,
    role: str,
    settings: Settings,
    *,
    expires_delta: timedelta | None = None,
    now: datetime | None = None,
) -> str:
    """Return a signed JWT.

    TODO: payload = {"sub": str(user_id), "role": role, "iat": issued, "exp": issued + ttl} where
    ``issued = now or datetime.now(UTC)`` and ``ttl = expires_delta`` if given else
    ``settings.access_token_ttl_minutes`` minutes. ``sub`` MUST be a string (PyJWT >= 2.10 rejects
    an int on decode). Sign with ``settings.jwt_secret`` / ``settings.jwt_algorithm``.
    ``expires_delta`` / ``now`` exist so tests can mint expired tokens without sleeping.
    """
    raise NotImplementedError("TODO: create_access_token")


def decode_access_token(token: str, settings: Settings) -> dict[str, Any]:
    """Validate ``token`` and return its claims, or raise ``AuthenticationError``.

    TODO: ``jwt.decode`` with ``algorithms=[settings.jwt_algorithm]`` (NEVER trust the token's own
    ``alg`` header - that is how "alg=none" attacks work) and ``options={"require": ["exp", "sub"]}``
    so a token without an expiry is refused. Map ``jwt.ExpiredSignatureError`` and every other
    ``jwt.PyJWTError`` to ``AuthenticationError`` (401), never let a PyJWT exception escape.
    """
    raise NotImplementedError("TODO: decode_access_token")
