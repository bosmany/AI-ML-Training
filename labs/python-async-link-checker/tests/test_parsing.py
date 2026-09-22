"""Pure helpers: URL handling, HTML link extraction, classification and the backoff schedule. No network."""
import asyncio
import socket

import httpx
import pytest

from lab import (CheckConfig, Status, backoff_delay, classify_exception, classify_status, extract_links,
                 is_same_host, make_timeout, normalize_url)


def test_extract_links_resolves_relative_urls_against_the_page_url():
    html = ('<a href="/abs">1</a><a href="rel">2</a><a href="../up">3</a><a href="?q=1">4</a>'
            '<a href="//other.test/x">5</a><a href="HTTP://Host.Test/UP#frag">6</a>')
    assert extract_links(html, "http://host.test/dir/page") == [
        "http://host.test/abs", "http://host.test/dir/rel", "http://host.test/up",
        "http://host.test/dir/page?q=1", "http://other.test/x", "http://host.test/UP"]


def test_extract_links_skips_non_http_links_drops_fragments_dedupes_and_survives_bad_html():
    html = """
      <a href="mailto:a@b.c">mail</a> <a href="javascript:void(0)">js</a> <a href="tel:123">tel</a>
      <a href="ftp://h/f">ftp</a> <a href="#top">top</a> <a href="">empty</a> <a>no href</a>
      <a href="/a#one">a</a> <a href="/a#two">a again</a> <a href="/b">b</a> <a href="http://[oops">bad</a>
      <a href="/c"><b>unclosed <a href="/d">nested</a> <div><p>
    """
    assert extract_links(html, "http://h.test/") == ["http://h.test/a", "http://h.test/b", "http://h.test/c",
                                                     "http://h.test/d"]
    assert extract_links("", "http://h.test/") == []
    assert extract_links("plain text, no markup", "http://h.test/") == []


def test_normalize_url_drops_fragment_lowercases_host_and_keeps_the_query():
    assert normalize_url("HTTP://Example.COM/a/b?x=1&y=2#section") == "http://example.com/a/b?x=1&y=2"
    assert normalize_url("http://example.com") == "http://example.com/"
    assert normalize_url("http://example.com:8080/") == "http://example.com:8080/"
    assert normalize_url("http://a/x") != normalize_url("http://a/x?v=1"), "different queries are different pages"


def test_is_same_host_compares_host_and_port_case_insensitively():
    assert is_same_host("http://Example.com/a", "http://example.com/b?x")
    assert not is_same_host("http://example.com/", "http://www.example.com/")
    assert not is_same_host("http://127.0.0.1:8001/", "http://127.0.0.1:8002/"), "another port is another server"


def test_classify_status_maps_code_classes():
    assert [classify_status(c) for c in (200, 204, 299)] == [Status.OK] * 3
    assert [classify_status(c) for c in (400, 404, 410, 429, 499)] == [Status.CLIENT_ERROR] * 5
    assert [classify_status(c) for c in (500, 503, 599)] == [Status.SERVER_ERROR] * 3
    assert classify_status(304) is Status.CLIENT_ERROR, "a 3xx that could not be followed is not a success"
    assert Status.OK.is_broken is False and Status.REDIRECT.is_broken is False
    assert all(s.is_broken for s in Status if s not in (Status.OK, Status.REDIRECT))


def test_classify_exception_separates_timeouts_dns_and_connection_errors():
    assert classify_exception(httpx.ReadTimeout("slow"))[0] is Status.TIMEOUT
    assert classify_exception(httpx.ConnectTimeout("slow"))[0] is Status.TIMEOUT
    assert classify_exception(TimeoutError())[0] is Status.TIMEOUT, "asyncio.timeout() raises TimeoutError"
    dns = httpx.ConnectError("lookup failed")
    dns.__cause__ = socket.gaierror(-2, "Name or service not known")
    assert classify_exception(dns)[0] is Status.DNS_ERROR
    assert classify_exception(httpx.ConnectError("refused"))[0] is Status.CONNECTION_ERROR
    assert classify_exception(httpx.ReadError("reset"))[0] is Status.CONNECTION_ERROR
    assert classify_exception(ConnectionResetError())[0] is Status.CONNECTION_ERROR
    status, message = classify_exception(httpx.ReadTimeout("slow"))
    assert message, "a message is returned for the report"
    with pytest.raises(ValueError):
        classify_exception(ValueError("a programming error must not be reported as a broken link"))


def test_backoff_delay_doubles_and_is_capped():
    assert [backoff_delay(n, 0.5) for n in range(4)] == [0.5, 1.0, 2.0, 4.0]
    assert backoff_delay(10, 1.0) == 30.0, "default cap is 30 seconds"
    assert backoff_delay(10, 1.0, cap=5.0) == 5.0
    assert backoff_delay(3, 0.0) == 0.0


def test_config_validation_and_timeout_object():
    CheckConfig().validate()
    for bad in ({"concurrency": 0}, {"concurrency": -1}, {"timeout": 0}, {"connect_timeout": -1.0}, {"retries": -1},
                {"max_redirects": -1}, {"backoff_base": -0.1}):
        with pytest.raises(ValueError):
            CheckConfig(**bad).validate()
    timeout = make_timeout(CheckConfig(timeout=7.0, connect_timeout=2.0))
    assert isinstance(timeout, httpx.Timeout)
    assert (timeout.connect, timeout.read) == (2.0, 7.0), "connect timeout is separate from the total/read timeout"
