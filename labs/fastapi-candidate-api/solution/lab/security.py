"""Password hashing and JWT helpers (reference solution)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
import jwt

from lab.errors import AuthenticationError
from lab.settings import Settings

BCRYPT_MAX_BYTES = 72


def hash_password(password: str) -> str:
    raw = password.encode("utf-8")
    if len(raw) > BCRYPT_MAX_BYTES:
        # bcrypt only looks at the first 72 bytes; bcrypt>=5 raises, older versions silently truncate.
        # Be explicit and consistent: refuse.
        raise ValueError("password longer than 72 bytes is not supported by bcrypt")
    return bcrypt.hashpw(raw, bcrypt.gensalt()).decode("ascii")


def verify_password(password: str, hashed: str) -> bool:
    raw = password.encode("utf-8")
    if len(raw) > BCRYPT_MAX_BYTES:
        return False  # can never match a hash we produced; must not raise (login would 500)
    try:
        return bcrypt.checkpw(raw, hashed.encode("ascii"))
    except ValueError:  # malformed hash
        return False


def create_access_token(
    user_id: int,
    role: str,
    settings: Settings,
    *,
    expires_delta: timedelta | None = None,
    now: datetime | None = None,
) -> str:
    issued = now or datetime.now(UTC)
    ttl = expires_delta if expires_delta is not None else timedelta(minutes=settings.access_token_ttl_minutes)
    payload: dict[str, Any] = {
        "sub": str(user_id),  # PyJWT >= 2.10 rejects a non-string subject
        "role": role,
        "iat": issued,
        "exp": issued + ttl,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str, settings: Settings) -> dict[str, Any]:
    try:
        return jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],  # never trust the header's "alg"
            options={"require": ["exp", "sub"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise AuthenticationError("Token has expired") from exc
    except jwt.PyJWTError as exc:
        raise AuthenticationError("Invalid token") from exc
