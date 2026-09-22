"""Pure URL and HTML helpers (no network)."""
from __future__ import annotations

from html.parser import HTMLParser  # noqa: F401  (hint: subclass it and collect <a href>)
from urllib.parse import urljoin, urlsplit, urlunsplit  # noqa: F401


def normalize_url(url: str) -> str:
    """Canonical form used for de-duplication.

    TODO: drop the fragment, lowercase scheme and host, turn an empty path into ``/``, keep the query string.
    ``HTTP://Example.COM/a?x=1#top`` -> ``http://example.com/a?x=1``; ``http://example.com`` -> ``http://example.com/``.
    (``urlsplit`` / ``urlunsplit`` do the heavy lifting.)
    """
    raise NotImplementedError


def is_same_host(url: str, other: str) -> bool:
    """True when both URLs have the same host AND port, ignoring case (``www.`` is a different host).

    TODO: compare ``urlsplit(...).netloc`` lowercased.
    """
    raise NotImplementedError


def extract_links(html: str, base_url: str) -> list[str]:
    """Absolute, normalized http(s) URLs of every ``<a href>``, in first-seen order, without duplicates.

    TODO:
    - collect hrefs with ``html.parser.HTMLParser`` (never a regex); tolerate malformed/unclosed markup
    - skip empty and fragment-only (``#top``) hrefs, ``<a>`` without href, and every scheme except http/https
      (``mailto:``, ``javascript:``, ``tel:``, ``ftp:``)
    - resolve with ``urljoin(base_url, href)`` (handles ``../x``, ``?q=1``, ``//host/p``), then ``normalize_url``
    - an href that makes ``urljoin`` raise ``ValueError`` (e.g. ``http://[oops``) is skipped, not fatal
    """
    raise NotImplementedError
