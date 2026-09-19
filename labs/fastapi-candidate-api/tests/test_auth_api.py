"""Register / login over HTTP."""

from __future__ import annotations

from conftest import PASSWORD, bearer


def test_register_creates_a_recruiter_and_never_returns_password_material(client):
    response = client.post("/auth/register", json={"email": "New.Person@Example.com", "password": PASSWORD})
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["email"] == "new.person@example.com", "emails are normalised to lower case"
    assert body["role"] == "recruiter"
    assert isinstance(body["id"], int)
    assert not {"password", "hashed_password"} & set(body), f"leaked credential fields: {sorted(body)}"


def test_registering_the_same_email_twice_conflicts_case_insensitively(client):
    assert client.post("/auth/register", json={"email": "dup@example.com", "password": PASSWORD}).status_code == 201
    response = client.post("/auth/register", json={"email": "DUP@example.com", "password": PASSWORD})
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "conflict"


def test_register_validates_email_and_password_rules_including_the_bcrypt_byte_limit(client):
    bad_payloads = {
        "not an email": {"email": "not-an-email", "password": PASSWORD},
        "password too short": {"email": "a@example.com", "password": "short"},
        "73 ASCII bytes": {"email": "b@example.com", "password": "x" * 73},
        "19 emoji = 76 bytes": {"email": "c@example.com", "password": "\U0001f512" * 19},
        "missing password": {"email": "d@example.com"},
        "client tries to pick its own role": {"email": "e@example.com", "password": PASSWORD, "role": "admin"},
    }
    for label, payload in bad_payloads.items():
        response = client.post("/auth/register", json=payload)
        assert response.status_code == 422, f"{label}: expected 422, got {response.status_code} {response.text}"
        assert response.json()["error"]["code"] == "validation_error"

    exactly_72 = "p" * 72
    assert client.post("/auth/register", json={"email": "ok@example.com", "password": exactly_72}).status_code == 201
    assert client.post("/auth/login", json={"email": "ok@example.com", "password": exactly_72}).status_code == 200


def test_login_returns_a_bearer_token_that_authenticates_later_requests(client, recruiter):
    response = client.post("/auth/login", json={"email": recruiter["email"].upper(), "password": PASSWORD})
    assert response.status_code == 200, "email lookup must be case-insensitive"
    body = response.json()
    assert body["token_type"] == "bearer" and body["access_token"]

    created = client.post(
        "/candidates",
        json={"name": "Grace", "email": "grace@example.com", "city": "NYC", "score": 95},
        headers=bearer(body["access_token"]),
    )
    assert created.status_code == 201, created.text


def test_login_failures_are_401_and_do_not_reveal_which_emails_exist(client, recruiter):
    wrong_password = client.post("/auth/login", json={"email": recruiter["email"], "password": "wrong-password-1"})
    unknown_email = client.post("/auth/login", json={"email": "ghost@example.com", "password": PASSWORD})
    for response in (wrong_password, unknown_email):
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "unauthorized"
        assert response.headers.get("www-authenticate") == "Bearer"
    assert wrong_password.json() == unknown_email.json(), "identical bodies, or attackers can enumerate accounts"


def test_login_with_an_absurdly_long_password_is_a_clean_401_not_a_500(client, recruiter):
    response = client.post("/auth/login", json={"email": recruiter["email"], "password": "a" * 500})
    assert response.status_code == 401, f"got {response.status_code}: bcrypt's 72-byte limit must not crash login"
