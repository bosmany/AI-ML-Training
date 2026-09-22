"""Target-URL validation (starter)."""

from __future__ import annotations

from collections.abc import Iterable
from urllib.parse import urlsplit  # noqa: F401

from lab.errors import ValidationFailed  # noqa: F401

MAX_URL_LENGTH = 2048
ALLOWED_SCHEMES = frozenset({"http", "https"})


def validate_target_url(url: str, own_hosts: Iterable[str] = ()) -> str:
    """Return the URL stripped of surrounding whitespace and otherwise UNCHANGED, or raise ValidationFailed.

    TODO, in this order:
      1. strip; empty -> error;
      2. longer than ``MAX_URL_LENGTH`` -> error whose message contains the limit ("2048"); exactly 2048 is fine;
      3. any whitespace / control character inside -> error;
      4. ``urlsplit`` (it can raise ``ValueError``, e.g. for a bad port - also touch ``.port``) ;
      5. scheme (case-insensitive) must be in ``ALLOWED_SCHEMES``: this is what blocks ``javascript:``,
         ``file:``, ``data:`` and scheme-less ``//host`` / ``example.com``;
      6. there must be a host (``parts.hostname``);
      7. host (case-insensitive, port ignored - ``hostname`` already drops it) in ``own_hosts`` -> error whose
         message contains "loop". Compare WHOLE hosts: ``short.test.evil.com`` is not ``short.test``.

    Do NOT normalise: never use pydantic's ``AnyHttpUrl`` value or ``urlunsplit`` for what you return -
    the redirect must go exactly where the user asked (``http://example.com`` stays without a trailing slash).
    """
    raise NotImplementedError("TODO: implement validate_target_url")
