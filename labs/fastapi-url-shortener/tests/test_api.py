"""HTTP contract tests: status codes, response schema, headers, error envelope."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from conftest import AlwaysSame, FakeClock, SequenceGenerator

URL = "https://example.com/some/page?x=1&y=two#frag"


def create(client: TestClient, **body) -> dict:  # noqa: ANN003
    body.setdefault("url", URL)
    r = client.post("/links", json=body)
    assert r.status_code == 201, r.text
    return r.json()


def assert_envelope(response, status: int, code: str) -> None:  # noqa: ANN001
    assert response.status_code == status, response.text
    error = response.json()["error"]
    assert error["code"] == code, error
    assert isinstance(error["message"], str) and error["message"]


# ------------------------------------------------------------------ create
def test_create_returns_201_with_a_seven_char_base62_code_and_full_schema(client: TestClient) -> None:
    r = client.post("/links", json={"url": URL})
    assert r.status_code == 201
    body = r.json()
    assert set(body) == {"code", "short_url", "url", "permanent", "created_at", "expires_at", "clicks", "expired"}
    assert len(body["code"]) == 7 and body["code"].isalnum()
    assert body["short_url"] == f"http://testserver/{body['code']}"
    assert (body["url"], body["clicks"], body["permanent"], body["expires_at"], body["expired"]) == (URL, 0, False, None, False)
    assert body["created_at"].startswith("2030-01-01T12:00:00")
    assert create(client, ttl_seconds=3600)["expires_at"].startswith("2030-01-01T13:00:00")


def test_custom_code_is_used_and_a_duplicate_returns_409_in_the_error_envelope(client: TestClient) -> None:
    assert create(client, custom_code="my-code")["code"] == "my-code"
    assert client.get("/my-code").status_code == 302
    assert_envelope(client.post("/links", json={"url": URL, "custom_code": "my-code"}), 409, "conflict")


def test_forced_generator_collision_is_retried_and_returns_a_unique_code(make_client) -> None:  # noqa: ANN001
    c = make_client(SequenceGenerator(["aaaaaaa", "aaaaaaa", "bbbbbbb"]))
    assert create(c)["code"] == "aaaaaaa"
    assert create(c)["code"] == "bbbbbbb"
    assert c.get("/aaaaaaa").headers["location"] == URL and c.get("/bbbbbbb").status_code == 302


def test_exhausted_collision_retries_return_503_not_500(make_client) -> None:  # noqa: ANN001
    c = make_client(AlwaysSame("aaaaaaa"))
    create(c)
    assert_envelope(c.post("/links", json={"url": URL}), 503, "code_generation_failed")


def test_unsafe_or_malformed_urls_are_rejected_with_422(client: TestClient) -> None:
    for url in ["javascript:alert(1)", "file:///etc/passwd", "ftp://example.com/x", "not a url", "http://", "", "https://e.com/" + "a" * 2100]:
        assert_envelope(client.post("/links", json={"url": url}), 422, "validation_error")
    for url in ["http://short.test/abc", "https://SHORT.test:8443/", "http://testserver/x"]:  # redirect loops
        assert_envelope(client.post("/links", json={"url": url}), 422, "validation_error")


def test_reserved_codes_and_malformed_request_bodies_return_422_envelope(client: TestClient) -> None:
    for code in ["docs", "links", "openapi.json", "redoc", "DOCS"]:
        assert_envelope(client.post("/links", json={"url": URL, "custom_code": code}), 422, "validation_error")
    for body in [{}, {"url": 42}, {"url": URL, "ttl_seconds": 0}, {"url": URL, "ttl_seconds": -5}, {"url": URL, "custom_code": "a b"}, {"url": URL, "bogus": 1}]:
        assert_envelope(client.post("/links", json=body), 422, "validation_error")


# ------------------------------------------------------------------ redirect
def test_redirect_is_302_or_301_and_location_matches_the_stored_url_exactly(client: TestClient) -> None:
    temp, perm = create(client)["code"], create(client, permanent=True)["code"]
    r = client.get(f"/{temp}")
    assert r.status_code == 302
    assert r.headers["location"] == URL, "no normalisation of the target URL is allowed"
    assert client.get(f"/{perm}").status_code == 301


def test_unknown_404_expired_410_and_deleted_404(client: TestClient, clock: FakeClock) -> None:
    expiring = create(client, ttl_seconds=60)["code"]
    deleted = create(client)["code"]
    assert client.delete(f"/links/{deleted}").status_code == 204
    clock.advance(59)
    assert client.get(f"/{expiring}").status_code == 302
    clock.advance(1)
    assert_envelope(client.get(f"/{expiring}"), 410, "gone")
    assert_envelope(client.get(f"/{deleted}"), 404, "not_found")
    assert_envelope(client.get("/nosuchcode"), 404, "not_found")


def test_clicks_are_counted_per_redirect_only(client: TestClient, clock: FakeClock) -> None:
    code = create(client, ttl_seconds=100)["code"]
    for _ in range(3):
        client.get(f"/{code}")
    assert client.get(f"/links/{code}").json()["clicks"] == 3, "reading stats must not add clicks"
    clock.advance(100)
    client.get(f"/{code}")  # 410
    info = client.get(f"/links/{code}").json()
    assert (info["clicks"], info["expired"]) == (3, True), "a 410 is not a click; stats stay readable"


# ------------------------------------------------------------------ read / update / delete
def test_get_and_put_link(client: TestClient) -> None:
    code = create(client)["code"]
    assert client.get(f"/links/{code}").json()["url"] == URL
    r = client.put(f"/links/{code}", json={"url": "https://new.example/x"})
    assert r.status_code == 200 and r.json()["url"] == "https://new.example/x"
    assert client.get(f"/{code}").headers["location"] == "https://new.example/x"
    assert_envelope(client.put(f"/links/{code}", json={"url": "javascript:alert(1)"}), 422, "validation_error")
    assert_envelope(client.put("/links/nope", json={"url": URL}), 404, "not_found")
    assert_envelope(client.get("/links/nope"), 404, "not_found")


def test_delete_returns_204_then_404(client: TestClient) -> None:
    code = create(client)["code"]
    r = client.delete(f"/links/{code}")
    assert r.status_code == 204 and r.content == b""
    assert_envelope(client.delete(f"/links/{code}"), 404, "not_found")
    assert_envelope(client.get(f"/links/{code}"), 404, "not_found")


# ------------------------------------------------------------------ pagination
def test_list_pagination_walks_all_pages_and_reports_total(client: TestClient) -> None:
    assert client.get("/links").json() == {"items": [], "total": 0, "limit": 10, "offset": 0}
    codes = [create(client, custom_code=f"link{i}")["code"] for i in range(5)]
    seen: list[str] = []
    for offset, expected_len in ((0, 2), (2, 2), (4, 1), (6, 0)):
        page = client.get("/links", params={"limit": 2, "offset": offset}).json()
        assert (page["total"], page["limit"], page["offset"], len(page["items"])) == (5, 2, offset, expected_len)
        seen += [i["code"] for i in page["items"]]
    assert seen == codes


def test_list_rejects_out_of_range_paging_parameters(client: TestClient) -> None:
    for params in [{"limit": 0}, {"limit": 101}, {"offset": -1}, {"limit": "x"}]:
        assert_envelope(client.get("/links", params=params), 422, "validation_error")


# ------------------------------------------------------------------ routing
def test_docs_and_openapi_are_not_shadowed_by_the_code_route(client: TestClient) -> None:
    assert client.get("/docs").status_code == 200
    assert client.get("/openapi.json").json()["paths"].get("/links") is not None
    assert client.get("/links").status_code == 200, "/links is the list endpoint, not a short code"
