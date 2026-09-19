"""Candidate CRUD: pagination, filtering, sorting, auth and roles."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import jwt
from conftest import bearer, candidate_payload

from lab.security import create_access_token


def row(name: str, city: str, score: float, email: str | None = None) -> dict:
    return {"name": name, "city": city, "score": score, "email": email or f"{name.lower()}@example.com"}


# --------------------------------------------------------------------------- reads (public)
def test_list_is_public_and_a_fresh_database_starts_empty(client):
    response = client.get("/candidates")
    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0, "page": 1, "page_size": 10, "pages": 0}


def test_get_candidate_by_id_404_and_invalid_id(client, seed_candidates):
    (candidate_id,) = seed_candidates([row("Ada", "London", 91)])
    found = client.get(f"/candidates/{candidate_id}")
    assert found.status_code == 200
    assert found.json()["name"] == "Ada" and found.json()["score"] == 91

    missing = client.get("/candidates/999")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "not_found"
    assert "999" in missing.json()["error"]["message"]

    assert client.get("/candidates/abc").status_code == 422


def test_pagination_boundaries_on_25_rows(client, seed_candidates):
    ids = seed_candidates([row(f"c{i:02d}", "Cairo", i) for i in range(25)])

    first = client.get("/candidates").json()  # defaults: page 1, size 10
    assert (first["page"], first["page_size"], first["total"], first["pages"]) == (1, 10, 25, 3)
    assert [c["id"] for c in first["items"]] == ids[:10]

    last = client.get("/candidates", params={"page": 3, "page_size": 10}).json()
    assert [c["id"] for c in last["items"]] == ids[20:], "the last page holds the remaining 5 rows"

    beyond = client.get("/candidates", params={"page": 4, "page_size": 10})
    assert beyond.status_code == 200, "a page past the end is an empty page, not an error"
    assert beyond.json()["items"] == [] and beyond.json()["total"] == 25 and beyond.json()["pages"] == 3

    exact = client.get("/candidates", params={"page_size": 25}).json()
    assert len(exact["items"]) == 25 and exact["pages"] == 1
    assert client.get("/candidates", params={"page_size": 100}).status_code == 200


def test_invalid_pagination_and_sorting_parameters_are_422(client):
    bad_queries = [
        {"page": 0},
        {"page": -1},
        {"page_size": 0},
        {"page_size": 101},
        {"page_size": "many"},
        {"min_score": -0.1},
        {"min_score": 100.1},
        {"sort": "email"},
    ]
    for params in bad_queries:
        response = client.get("/candidates", params=params)
        assert response.status_code == 422, f"{params}: expected 422, got {response.status_code}"
        assert response.json()["error"]["code"] == "validation_error"


def test_filters_min_score_is_inclusive_city_is_case_insensitive_total_counts_matches(client, seed_candidates):
    seed_candidates(
        [
            row("A", "Cairo", 90),
            row("B", "cairo", 75),
            row("C", "Berlin", 75),
            row("D", "Berlin", 60),
            row("E", "Cairo", 50),
        ]
    )
    names = lambda params: [c["name"] for c in client.get("/candidates", params=params).json()["items"]]  # noqa: E731

    assert names({"min_score": 75}) == ["A", "B", "C"], "min_score is inclusive (>=)"
    assert names({"city": "CAIRO"}) == ["A", "B", "E"]
    assert names({"city": "cairo", "min_score": 75}) == ["A", "B"], "filters combine with AND"
    assert names({"min_score": 0}) == ["A", "B", "C", "D", "E"]
    assert names({"city": "Atlantis"}) == []

    page = client.get("/candidates", params={"city": "cairo", "min_score": 75, "page_size": 1}).json()
    assert (page["total"], page["pages"], len(page["items"])) == (2, 2, 1), "total/pages describe the FILTERED set"
    empty = client.get("/candidates", params={"city": "Atlantis"}).json()
    assert (empty["total"], empty["pages"]) == (0, 0)


def test_sorting_orders_and_a_stable_tie_break_keeps_pages_consistent(client, seed_candidates):
    ids = seed_candidates(
        [row("Charlie", "X", 75), row("alice", "X", 90), row("Bob", "X", 75), row("dave", "X", 60), row("Eve", "X", 90)]
    )
    names = lambda sort: [c["name"] for c in client.get("/candidates", params={"sort": sort}).json()["items"]]  # noqa: E731

    assert names("-score") == ["alice", "Eve", "Charlie", "Bob", "dave"], "ties are broken by id ascending"
    assert names("score") == ["dave", "Charlie", "Bob", "alice", "Eve"]
    assert names("id") == ["Charlie", "alice", "Bob", "dave", "Eve"]
    assert names("name") == ["alice", "Bob", "Charlie", "dave", "Eve"], "name sort ignores letter case"
    assert names("-name") == ["Eve", "dave", "Charlie", "Bob", "alice"]

    seen: list[int] = []
    for page in (1, 2, 3):
        body = client.get("/candidates", params={"sort": "-score", "page_size": 2, "page": page}).json()
        seen += [c["id"] for c in body["items"]]
    assert sorted(seen) == sorted(ids) and len(seen) == len(set(seen)), "no row may repeat or vanish across pages"


# --------------------------------------------------------------------------- auth on writes
def test_write_endpoints_reject_missing_malformed_expired_tampered_and_orphaned_tokens(
    client, settings, recruiter
):
    def post(headers):
        return client.post("/candidates", json=candidate_payload(), headers=headers)

    valid = create_access_token(recruiter["id"], "recruiter", settings)
    expired = create_access_token(recruiter["id"], "recruiter", settings, expires_delta=timedelta(seconds=-10))
    other_secret = jwt.encode(
        {"sub": str(recruiter["id"]), "exp": datetime.now(UTC) + timedelta(minutes=5)},
        "an-entirely-different-secret-0123456789-abcdef",
        algorithm="HS256",
    )
    nobody = create_access_token(987654, "recruiter", settings)
    cases = {
        "no Authorization header": {},
        "wrong scheme": {"Authorization": f"Token {valid}"},
        "Bearer without a token": {"Authorization": "Bearer"},
        "not a jwt": bearer("garbage"),
        "expired": bearer(expired),
        "signed with another secret": bearer(other_secret),
        "user id that no longer exists": bearer(nobody),
    }
    for label, headers in cases.items():
        response = post(headers)
        assert response.status_code == 401, f"{label}: expected 401, got {response.status_code} {response.text}"
        assert response.json()["error"]["code"] == "unauthorized"
        assert response.headers.get("www-authenticate") == "Bearer", f"{label}: missing WWW-Authenticate"

    assert client.patch("/candidates/1", json={"score": 1}).status_code == 401
    assert client.delete("/candidates/1").status_code == 401
    assert client.get("/candidates").json()["total"] == 0, "nothing may have been written"
    assert post(bearer(valid)).status_code == 201, "sanity: the valid token does work"


def test_role_comes_from_the_database_not_from_a_forgeable_claim(client, settings, recruiter, seed_candidates):
    (candidate_id,) = seed_candidates([row("Ada", "London", 91)])
    forged = jwt.encode(
        {"sub": str(recruiter["id"]), "role": "admin", "exp": datetime.now(UTC) + timedelta(minutes=5)},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    response = client.delete(f"/candidates/{candidate_id}", headers=bearer(forged))
    assert response.status_code == 403, "a token claiming role=admin for a recruiter row must not grant admin"


# --------------------------------------------------------------------------- create
def test_create_returns_201_stamps_creator_normalises_email_and_queues_a_background_event(client, recruiter):
    response = client.post(
        "/candidates", json=candidate_payload(email="Ada@Example.COM"), headers=recruiter["headers"]
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["email"] == "ada@example.com"
    assert body["created_by"] == recruiter["id"]
    assert (body["name"], body["city"], body["score"]) == ("Ada Lovelace", "London", 88.5)
    assert body["id"] and body["created_at"]

    assert client.app.state.events == [
        {"name": "candidate.created", "candidate_id": body["id"], "email": "ada@example.com"}
    ], "the background task must run after a successful create"
    assert client.get(f"/candidates/{body['id']}").json()["email"] == "ada@example.com"


def test_create_rejects_invalid_bodies_with_422_and_duplicates_with_409_and_queues_nothing(client, recruiter):
    invalid = {
        "score above 100": candidate_payload(score=100.5),
        "negative score": candidate_payload(score=-1),
        "blank name": candidate_payload(name="   "),
        "malformed email": candidate_payload(email="nope"),
        "score is text": candidate_payload(score="high"),
    }
    for label, payload in invalid.items():
        response = client.post("/candidates", json=payload, headers=recruiter["headers"])
        assert response.status_code == 422, f"{label}: expected 422, got {response.status_code}"
        assert response.json()["error"]["code"] == "validation_error"
    missing = candidate_payload()
    del missing["city"]
    assert client.post("/candidates", json=missing, headers=recruiter["headers"]).status_code == 422

    assert client.post("/candidates", json=candidate_payload(), headers=recruiter["headers"]).status_code == 201
    duplicate = client.post("/candidates", json=candidate_payload(email="ADA@example.com"), headers=recruiter["headers"])
    assert duplicate.status_code == 409 and duplicate.json()["error"]["code"] == "conflict"
    assert len(client.app.state.events) == 1, "failed creates must not trigger the background task"
    assert client.get("/candidates").json()["total"] == 1


# --------------------------------------------------------------------------- update
def test_patch_updates_only_the_fields_sent(client, recruiter, seed_candidates):
    (candidate_id,) = seed_candidates([row("Ada", "London", 91)])
    url = f"/candidates/{candidate_id}"

    updated = client.patch(url, json={"score": 55}, headers=recruiter["headers"])
    assert updated.status_code == 200, updated.text
    assert (updated.json()["score"], updated.json()["name"], updated.json()["city"]) == (55, "Ada", "London")

    noop = client.patch(url, json={}, headers=recruiter["headers"])
    assert noop.status_code == 200 and noop.json()["score"] == 55, "an empty patch changes nothing"

    same_email = client.patch(url, json={"email": "ADA@example.com", "city": "Paris"}, headers=recruiter["headers"])
    assert same_email.status_code == 200, "re-sending your own email is not a conflict"
    assert client.get(url).json()["city"] == "Paris"


def test_patch_error_paths_404_409_and_422(client, recruiter, seed_candidates):
    first, second = seed_candidates([row("Ada", "London", 91), row("Bob", "Paris", 70)])

    assert client.patch("/candidates/999", json={"score": 1}, headers=recruiter["headers"]).status_code == 404

    conflict = client.patch(f"/candidates/{first}", json={"email": "bob@example.com"}, headers=recruiter["headers"])
    assert conflict.status_code == 409 and conflict.json()["error"]["code"] == "conflict"

    for body in ({"score": 101}, {"name": ""}, {"name": None}, {"score": None}):
        response = client.patch(f"/candidates/{second}", json=body, headers=recruiter["headers"])
        assert response.status_code == 422, f"{body}: expected 422, got {response.status_code} {response.text}"
        assert response.json()["error"]["code"] == "validation_error"
    assert client.get(f"/candidates/{second}").json()["name"] == "Bob", "rejected patches change nothing"


# --------------------------------------------------------------------------- delete
def test_delete_requires_admin_and_removes_the_row(client, recruiter, admin, seed_candidates):
    (candidate_id,) = seed_candidates([row("Ada", "London", 91)])
    url = f"/candidates/{candidate_id}"

    forbidden = client.delete(url, headers=recruiter["headers"])
    assert forbidden.status_code == 403, "a recruiter may create/update but not delete"
    assert forbidden.json()["error"]["code"] == "forbidden"
    assert client.get(url).status_code == 200, "a forbidden delete must not delete"

    deleted = client.delete(url, headers=admin["headers"])
    assert deleted.status_code == 204 and deleted.content == b""
    assert client.get(url).status_code == 404
    assert client.delete(url, headers=admin["headers"]).status_code == 404, "deleting twice: second is 404"
