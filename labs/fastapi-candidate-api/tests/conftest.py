"""Shared fixtures. Every test gets its own app and its own fresh in-memory database."""

from __future__ import annotations

import asyncio
import os
import sys
from collections.abc import AsyncIterator, Callable, Iterator
from pathlib import Path

TARGET = os.environ.get("LAB_TARGET", "starter")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / TARGET))
sys.dont_write_bytecode = True

import bcrypt  # noqa: E402
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from lab.app import create_app  # noqa: E402
from lab.db import get_session, init_models  # noqa: E402
from lab.models import Candidate, User  # noqa: E402
from lab.settings import Settings  # noqa: E402

RECRUITER_EMAIL = "recruiter@example.com"
ADMIN_EMAIL = "admin@example.com"
PASSWORD = "correct-horse-battery"


@pytest.fixture
def settings() -> Settings:
    return Settings(
        database_url="sqlite+aiosqlite:///:memory:",
        jwt_secret="test-secret-that-is-comfortably-longer-than-sixty-four-bytes-0123456789abcdef",
    )


@pytest.fixture
def session_factory() -> Iterator[async_sessionmaker[AsyncSession]]:
    """A brand-new in-memory SQLite database (one shared connection) for each test."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    asyncio.run(init_models(engine))
    yield async_sessionmaker(engine, expire_on_commit=False)
    asyncio.run(engine.dispose())


@pytest.fixture
def app(settings: Settings, session_factory: async_sessionmaker[AsyncSession]):
    application = create_app(settings)

    async def override_get_session() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    application.dependency_overrides[get_session] = override_get_session
    return application


@pytest.fixture
def client(app) -> TestClient:
    return TestClient(app)


@pytest.fixture
def seed_user(session_factory) -> Callable[..., int]:
    """Insert a user straight into the DB (bypasses the API) and return its id."""

    def _seed(email: str, password: str, role: str) -> int:
        async def go() -> int:
            async with session_factory() as session:
                user = User(
                    email=email,
                    hashed_password=bcrypt.hashpw(password.encode(), bcrypt.gensalt(4)).decode(),
                    role=role,
                )
                session.add(user)
                await session.commit()
                return user.id

        return asyncio.run(go())

    return _seed


@pytest.fixture
def seed_candidates(session_factory) -> Callable[[list[dict]], list[int]]:
    """Insert candidate rows straight into the DB and return their ids (in insertion order)."""

    def _seed(rows: list[dict]) -> list[int]:
        async def go() -> list[int]:
            async with session_factory() as session:
                objs = [Candidate(**row) for row in rows]
                session.add_all(objs)
                await session.commit()
                return [o.id for o in objs]

        return asyncio.run(go())

    return _seed


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def login(client: TestClient) -> Callable[[str, str], dict[str, str]]:
    def _login(email: str, password: str) -> dict[str, str]:
        response = client.post("/auth/login", json={"email": email, "password": password})
        assert response.status_code == 200, f"login failed: {response.status_code} {response.text}"
        return bearer(response.json()["access_token"])

    return _login


@pytest.fixture
def recruiter(client: TestClient, login) -> dict:
    """Register through the public API, then log in. Returns {'id', 'email', 'headers'}."""
    response = client.post("/auth/register", json={"email": RECRUITER_EMAIL, "password": PASSWORD})
    assert response.status_code == 201, f"register failed: {response.status_code} {response.text}"
    return {"id": response.json()["id"], "email": RECRUITER_EMAIL, "headers": login(RECRUITER_EMAIL, PASSWORD)}


@pytest.fixture
def admin(seed_user, login) -> dict:
    """Admins cannot self-register (that would be privilege escalation) - seed one in the DB."""
    user_id = seed_user(ADMIN_EMAIL, PASSWORD, "admin")
    return {"id": user_id, "email": ADMIN_EMAIL, "headers": login(ADMIN_EMAIL, PASSWORD)}


def candidate_payload(**overrides) -> dict:
    payload = {"name": "Ada Lovelace", "email": "ada@example.com", "city": "London", "score": 88.5}
    payload.update(overrides)
    return payload
