"""Pure URL and HTML helpers (no network)."""
from __future__ import annotations

from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit, urlunsplit


class _AnchorCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.hrefs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "a":
            for name, value in attrs:
                if name == "href" and value:
                    self.hrefs.append(value)


def normalize_url(url: str) -> str:
    """Canonical form used for de-duplication: fragment dropped, scheme and host lowercased, empty path -> ``/``.

    The query string is kept. (Default ports are NOT stripped - a stretch goal.)
    """
    parts = urlsplit(url.strip())
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path or "/", parts.query, ""))


def is_same_host(url: str, other: str) -> bool:
    """True when both URLs have the same host AND port (case-insensitive)."""
    return urlsplit(url).netloc.lower() == urlsplit(other).netloc.lower()


def extract_links(html: str, base_url: str) -> list[str]:
    """Absolute, normalized http(s) URLs of every ``<a href>``, first-seen order, no duplicates.

    Skips empty and fragment-only hrefs, ``mailto:``, ``javascript:``, ``tel:``, ``ftp:`` and anything that
    cannot be parsed. Never raises on malformed HTML.
    """
    collector = _AnchorCollector()
    collector.feed(html)
    collector.close()
    seen: set[str] = set()
    links: list[str] = []
    for href in collector.hrefs:
        href = href.strip()
        if not href or href.startswith("#"):
            continue
        try:
            absolute = urljoin(base_url, href)
            if urlsplit(absolute).scheme not in ("http", "https"):
                continue
            link = normalize_url(absolute)
        except ValueError:
            continue
        if link not in seen:
            seen.add(link)
            links.append(link)
    return links
