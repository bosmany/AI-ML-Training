"""Application settings (scaffold - provided, do not edit)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    """Immutable configuration passed into ``create_app``.

    In production you would load these from environment variables; the lab keeps
    them explicit so tests can build an app with any configuration they like.
    """

    database_url: str = "sqlite+aiosqlite:///./candidates.db"
    jwt_secret: str = "dev-only-secret-change-me-0123456789abcdef"
    jwt_algorithm: str = "HS256"
    access_token_ttl_minutes: int = 30
