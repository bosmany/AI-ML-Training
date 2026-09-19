"""Password hashing and JWT helpers, tested as plain functions (no HTTP)."""

from __future__ import annotations

import base64
import json
from datetime import UTC, datetime, timedelta

import jwt
import pytest

from lab.errors import AuthenticationError
from lab.security import create_access_token, decode_access_token, hash_password, verify_password


def test_password_hash_is_salted_verifiable_and_rejects_wrong_or_malformed_input():
    first, second = hash_password("s3cret-pass"), hash_password("s3cret-pass")
    assert first != "s3cret-pass" and first.startswith("$2"), "store a bcrypt hash, never the plaintext"
    assert first != second, "each hash needs its own random salt"
    assert verify_password("s3cret-pass", first) is True
    assert verify_password("s3cret-pasS", first) is False
    assert verify_password("s3cret-pass", "not-a-bcrypt-hash") is False, "a corrupt stored hash means 'no'"


def test_bcrypt_72_byte_limit_is_enforced_explicitly_not_silently_truncated():
    exactly_72 = "a" * 72
    stored = hash_password(exactly_72)
    assert verify_password(exactly_72, stored) is True

    with pytest.raises(ValueError):
        hash_password("a" * 73)
    with pytest.raises(ValueError):
        hash_password("é" * 37)  # 37 characters but 74 UTF-8 bytes

    # A login attempt with a huge password must be a clean "wrong password", never an exception (500).
    assert verify_password("a" * 100, stored) is False
    assert verify_password(exactly_72 + "zzz", stored) is False, "chars after byte 72 must not be ignored"


def test_access_token_carries_string_subject_role_and_configured_lifetime(settings):
    issued = datetime(2024, 1, 1, 12, 0, tzinfo=UTC)
    token = create_access_token(42, "admin", settings, now=issued)

    claims = jwt.decode(
        token, settings.jwt_secret, algorithms=[settings.jwt_algorithm], options={"verify_exp": False}
    )
    assert claims["sub"] == "42" and isinstance(claims["sub"], str), "JWT 'sub' must be a string"
    assert claims["role"] == "admin"
    assert claims["exp"] - claims["iat"] == settings.access_token_ttl_minutes * 60
    assert claims["iat"] == int(issued.timestamp())

    fresh = decode_access_token(create_access_token(42, "admin", settings), settings)
    assert fresh["sub"] == "42" and fresh["role"] == "admin"


def test_expired_token_is_rejected(settings):
    token = create_access_token(1, "recruiter", settings, expires_delta=timedelta(seconds=-5))
    with pytest.raises(AuthenticationError):
        decode_access_token(token, settings)


def test_token_with_modified_payload_is_rejected(settings):
    token = create_access_token(1, "recruiter", settings)
    header, payload, signature = token.split(".")
    claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
    claims["role"] = "admin"
    forged = base64.urlsafe_b64encode(json.dumps(claims).encode()).rstrip(b"=").decode()
    with pytest.raises(AuthenticationError):
        decode_access_token(f"{header}.{forged}.{signature}", settings)


def test_tokens_signed_with_another_key_or_algorithm_are_rejected(settings):
    payload = {"sub": "1", "role": "admin", "exp": datetime.now(UTC) + timedelta(minutes=5)}
    bad_tokens = {
        "wrong secret": jwt.encode(payload, "some-other-secret-value-0123456789abcdef", algorithm="HS256"),
        "alg=none (unsigned)": jwt.encode(payload, key="", algorithm="none"),
        "alg=HS512 with the right secret": jwt.encode(payload, settings.jwt_secret, algorithm="HS512"),
        "garbage": "definitely.not.ajwt",
    }
    for label, token in bad_tokens.items():
        with pytest.raises(AuthenticationError):
            decode_access_token(token, settings)
            pytest.fail(f"{label} token was accepted")


def test_tokens_missing_required_claims_or_with_non_string_subject_are_rejected(settings):
    soon = datetime.now(UTC) + timedelta(minutes=5)
    cases = {
        "integer sub": {"sub": 1, "exp": soon},
        "no exp (would never expire)": {"sub": "1"},
        "no sub": {"exp": soon},
    }
    for label, payload in cases.items():
        token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
        with pytest.raises(AuthenticationError):
            decode_access_token(token, settings)
            pytest.fail(f"token with {label} was accepted")
