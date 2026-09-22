"""Target URL validation: safe schemes, sane length, no redirect loops, no normalisation."""

from __future__ import annotations

import pytest

from lab.errors import ValidationFailed
from lab.validation import validate_target_url

REJECTED = [
    "javascript:alert(1)",
    "JavaScript:alert(1)",
    "file:///etc/passwd",
    "ftp://example.com/x",
    "data:text/html;base64,PHNjcmlwdD4=",
    "//example.com/x",
    "example.com",
    "",
    "   ",
    "http://",
    "https:///path",
    "http://exa mple.com",
    "http://a.com/x\ny",
    "http://host:99999999/",
]


def test_http_and_https_urls_are_accepted_and_returned_byte_for_byte() -> None:
    for url in [
        "http://example.com",
        "https://example.com/a/b?x=1&y=%20z#frag",
        "HTTPS://Example.COM/Path",
        "http://example.com:8080/x",
        "http://[2001:db8::1]/x",
    ]:
        assert validate_target_url(url) == url, f"{url!r}: the stored URL must not be normalised"


def test_surrounding_whitespace_is_stripped() -> None:
    assert validate_target_url("  https://example.com/x \n") == "https://example.com/x"


def test_dangerous_schemes_and_malformed_urls_are_rejected() -> None:
    for url in REJECTED:
        with pytest.raises(ValidationFailed):
            validate_target_url(url)
            pytest.fail(f"{url!r} should have been rejected")


def test_url_length_limit_is_2048_inclusive() -> None:
    ok = "https://example.com/" + "a" * (2048 - len("https://example.com/"))
    assert len(ok) == 2048
    assert validate_target_url(ok) == ok
    with pytest.raises(ValidationFailed, match="2048"):
        validate_target_url(ok + "a")


def test_urls_pointing_at_the_service_are_rejected_but_lookalike_hosts_are_not() -> None:
    for url in ["http://short.test/abc", "https://SHORT.test:8443/x", "http://short.test"]:
        with pytest.raises(ValidationFailed, match="loop"):
            validate_target_url(url, own_hosts=["short.test"])
    for url in ("http://short.test.evil.com/x", "http://notshort.test/x", "http://evil.com/short.test"):
        assert validate_target_url(url, own_hosts=["short.test"]) == url
