"""Target-URL validation (reference solution)."""

from __future__ import annotations

from collections.abc import Iterable
from urllib.parse import urlsplit

from lab.errors import ValidationFailed

MAX_URL_LENGTH = 2048
ALLOWED_SCHEMES = frozenset({"http", "https"})


def validate_target_url(url: str, own_hosts: Iterable[str] = ()) -> str:
    """Return the URL stripped of surrounding whitespace and otherwise UNCHANGED, or raise ValidationFailed."""
    url = url.strip()
    if not url:
        raise ValidationFailed("url must not be empty")
    if len(url) > MAX_URL_LENGTH:
        raise ValidationFailed(f"url is longer than {MAX_URL_LENGTH} characters")
    if any(ch.isspace() or ord(ch) < 32 for ch in url):
        raise ValidationFailed("url must not contain whitespace or control characters")
    try:
        parts = urlsplit(url)
        host = parts.hostname
        parts.port  # noqa: B018 - raises ValueError for a malformed port
    except ValueError as exc:
        raise ValidationFailed(f"url is malformed: {exc}") from exc
    if parts.scheme.lower() not in ALLOWED_SCHEMES:
        raise ValidationFailed("only http and https URLs can be shortened")
    if not host:
        raise ValidationFailed("url must contain a host")
    if host.lower() in {h.lower() for h in own_hosts}:
        raise ValidationFailed("url points at this service (redirect loop)")
    return url
