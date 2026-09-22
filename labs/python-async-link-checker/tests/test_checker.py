"""Checking URLs against the local fixture server: classification, HEAD/GET, redirects, timeouts,
concurrency ceiling and retries - all verified with server-side counters, never with real time or network."""
import asyncio
import time

from fixture_server import closed_port

from lab import CheckConfig, Status, check_urls


class FakeSleep:
    """Records the backoff delays instead of waiting for them."""

    def __init__(self) -> None:
        self.delays: list[float] = []

    async def __call__(self, delay: float) -> None:
        self.delays.append(delay)


def check(site, paths, *, sleep=None, **config):
    urls = [p if p.startswith("http") else site.url(p) for p in paths]
    kwargs = {"sleep": sleep} if sleep is not None else {}
    return asyncio.run(check_urls(urls, CheckConfig(**config), **kwargs))


def test_a_healthy_page_is_ok_and_reports_status_latency_and_attempts(site):
    site.add("/ok", body="hi", delay=0.05)
    (result,) = check(site, ["/ok"])
    assert result.url == site.url("/ok") and result.status is Status.OK
    assert result.http_status == 200 and result.final_url is None and result.error is None
    assert result.attempts == 1
    assert result.latency >= 0.04, f"latency should include the 50 ms the server took, got {result.latency}"


def test_client_and_server_errors_are_classified_separately(site):
    site.add("/gone", status=404)
    site.add("/teapot", status=418)
    site.add("/boom", status=500)
    site.add("/down", status=503)
    got = {r.url.rsplit("/", 1)[1]: (r.status, r.http_status) for r in check(site, ["/gone", "/teapot", "/boom", "/down", "/missing"])}
    assert got == {"gone": (Status.CLIENT_ERROR, 404), "teapot": (Status.CLIENT_ERROR, 418),
                   "boom": (Status.SERVER_ERROR, 500), "down": (Status.SERVER_ERROR, 503),
                   "missing": (Status.CLIENT_ERROR, 404)}


def test_a_redirect_is_followed_and_reported_with_its_final_url(site):
    site.add("/old", status=301, headers={"Location": "/mid"})
    site.add("/mid", status=302, headers={"Location": "/new"})
    site.add("/new", body="fresh")
    (result,) = check(site, ["/old"])
    assert result.status is Status.REDIRECT and result.http_status == 200
    assert result.final_url == site.url("/new"), "final URL after following both hops"
    assert not result.status.is_broken


def test_a_redirect_to_a_missing_page_is_broken_and_keeps_the_final_url(site):
    site.add("/old", status=302, headers={"Location": "/nowhere"})
    (result,) = check(site, ["/old"])
    assert (result.status, result.http_status, result.final_url) == (Status.CLIENT_ERROR, 404, site.url("/nowhere"))


def test_redirect_chains_longer_than_the_limit_are_reported_not_followed_forever(site):
    site.add("/loop-a", status=302, headers={"Location": "/loop-b"})
    site.add("/loop-b", status=302, headers={"Location": "/loop-a"})
    (result,) = check(site, ["/loop-a"], max_redirects=4)
    assert result.status is Status.TOO_MANY_REDIRECTS and result.status.is_broken
    assert result.error
    assert len(site.requests) == 5, f"1 request + 4 followed hops, then stop; the server saw {len(site.requests)}"


def test_head_is_tried_first_and_a_plain_page_never_needs_a_get(site):
    site.add("/plain", body="x" * 100)
    (result,) = check(site, ["/plain"])
    assert result.status is Status.OK
    assert site.requests == [("HEAD", "/plain")], "HEAD only: cheaper for the server, no body downloaded"


def test_get_fallback_only_for_405_and_501_on_head(site):
    site.add("/no-head", head_status=405, body="ok")
    site.add("/not-impl", head_status=501, body="ok")
    site.add("/head-404", status=404)
    results = check(site, ["/no-head", "/not-impl", "/head-404"])
    assert [r.status for r in results] == [Status.OK, Status.OK, Status.CLIENT_ERROR]
    assert (site.count("/no-head", "HEAD"), site.count("/no-head", "GET")) == (1, 1)
    assert (site.count("/not-impl", "HEAD"), site.count("/not-impl", "GET")) == (1, 1)
    assert site.count("/head-404", "GET") == 0, "a HEAD 404 is an answer, not a reason to try GET"
    assert all(r.attempts == 1 for r in results), "the GET fallback is part of one attempt, not a retry"


def test_a_hanging_server_is_cut_off_at_the_timeout_and_reported_as_timeout(site):
    site.add("/hang", hang=True)
    started = time.monotonic()
    (result,) = check(site, ["/hang"], timeout=0.3, connect_timeout=0.3)
    elapsed = time.monotonic() - started
    assert result.status is Status.TIMEOUT and result.http_status is None and result.error
    assert elapsed < 3.0, f"a hung server must not block the run beyond the timeout (took {elapsed:.1f}s)"


def test_connection_refused_is_a_connection_error_not_a_crash(site):
    dead = f"http://127.0.0.1:{closed_port()}/x"
    (result,) = check(site, [dead], timeout=2.0)
    assert result.status is Status.CONNECTION_ERROR and result.http_status is None and result.error


def test_one_broken_url_does_not_abort_the_others(site):
    site.add("/ok", body="ok")
    site.add("/hang", hang=True)
    site.add("/boom", status=500)
    dead = f"http://127.0.0.1:{closed_port()}/"
    results = check(site, ["/ok", "/hang", "/boom", dead, "/missing"], timeout=0.3, connect_timeout=0.3)
    assert [r.status for r in results] == [Status.OK, Status.TIMEOUT, Status.SERVER_ERROR, Status.CONNECTION_ERROR,
                                           Status.CLIENT_ERROR]


def test_duplicate_urls_are_fetched_once_and_results_keep_first_seen_order(site):
    site.add("/slow", body="x", delay=0.15)
    site.add("/fast", body="x")
    seen = []
    urls = [site.url("/slow"), site.url("/fast"), site.url("/slow"), site.url("/fast"), site.url("/slow")]
    results = asyncio.run(check_urls(urls, CheckConfig(concurrency=4), on_result=seen.append))
    assert [r.url for r in results] == [site.url("/slow"), site.url("/fast")], "input order, not completion order"
    assert [s.url for s in seen] == [site.url("/fast"), site.url("/slow")], "on_result fires once per URL as each finishes"
    assert site.count("/slow") == 1 and site.count("/fast") == 1


def test_in_flight_requests_never_exceed_the_limit_and_do_reach_it(site):
    for i in range(12):
        site.add(f"/p{i}", body="x", hold_until_peak=3)  # server holds requests until 3 are in flight at once
    results = check(site, [f"/p{i}" for i in range(12)], concurrency=3)
    assert all(r.status is Status.OK for r in results)
    assert site.max_in_flight <= 3, f"server saw {site.max_in_flight} simultaneous requests with concurrency=3"
    assert site.max_in_flight == 3, "the limit should actually be used, not silently lower"
    site.max_in_flight = 0
    for i in range(5):
        site.add(f"/s{i}", body="x", delay=0.02)
    check(site, [f"/s{i}" for i in range(5)], concurrency=1)
    assert site.max_in_flight == 1, "concurrency=1 must serialise the requests"


def test_transient_failures_are_retried_with_exponential_backoff_until_success(site):
    site.add("/flaky", body="finally", fail_first=2)
    sleep = FakeSleep()
    (result,) = check(site, ["/flaky"], retries=3, backoff_base=0.5, sleep=sleep)
    assert result.status is Status.OK and result.attempts == 3
    assert site.count("/flaky") == 3, "two 503s then a 200"
    assert sleep.delays == [0.5, 1.0], f"backoff before retry 1 and 2, got {sleep.delays}"


def test_retries_stop_at_the_configured_number_and_client_errors_are_never_retried(site):
    site.add("/down", status=503)
    sleep = FakeSleep()
    (result,) = check(site, ["/down"], retries=2, backoff_base=1.0, sleep=sleep)
    assert (result.status, result.http_status, result.attempts) == (Status.SERVER_ERROR, 503, 3)
    assert site.count("/down") == 3, "1 attempt + 2 retries"
    assert sleep.delays == [1.0, 2.0], "no sleep after the final attempt"
    site.requests.clear()
    site.add("/down2", status=503)
    (again,) = check(site, ["/down2"])  # default: no retries
    assert again.attempts == 1 and site.count("/down2") == 1
    site.add("/gone", status=404)
    (client_error,) = check(site, ["/gone"], retries=5, sleep=sleep)
    assert client_error.status is Status.CLIENT_ERROR and client_error.attempts == 1, "4xx is never retried"
    assert site.count("/gone") == 1 and sleep.delays == [1.0, 2.0], "no extra sleeps for a 404"


def test_timeouts_are_retried_too(site):
    site.add("/hang", hang=True)
    sleep = FakeSleep()
    (result,) = check(site, ["/hang"], retries=1, timeout=0.25, connect_timeout=0.25, backoff_base=0.1, sleep=sleep)
    assert (result.status, result.attempts) == (Status.TIMEOUT, 2)
    assert site.count("/hang") == 2 and sleep.delays == [0.1]


def test_invalid_config_is_rejected_before_any_request(site):
    import pytest
    with pytest.raises(ValueError):
        check(site, ["/x"], concurrency=0)
    assert site.count() == 0
