"""Shared fixtures. Every test gets its own SQLite file in ``tmp_path`` (hermetic, nothing outside it)."""

from __future__ import annotations

import os
import sys
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

TARGET = os.environ.get("LAB_TARGET", "starter")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / TARGET))
sys.dont_write_bytecode = True

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.orm import Session, sessionmaker  # noqa: E402

from lab.app import create_app  # noqa: E402
from lab.db import init_db, make_engine, make_session_factory  # noqa: E402

START = datetime(2030, 1, 1, 12, 0, 0, tzinfo=UTC)
OWN_HOST = "short.test"


class FakeClock:
    """A controllable clock: tests move time instead of sleeping."""

    def __init__(self) -> None:
        self.now = START

    def __call__(self) -> datetime:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += timedelta(seconds=seconds)


class SequenceGenerator:
    """Code generator that replays a fixed list, so a test can FORCE a collision."""

    def __init__(self, codes: list[str]) -> None:
        self.codes = list(codes)
        self.calls = 0

    def __call__(self) -> str:
        if self.calls >= len(self.codes):
            raise AssertionError(f"generator called {self.calls + 1} times, only {len(self.codes)} codes queued")
        code = self.codes[self.calls]
        self.calls += 1
        return code


class AlwaysSame:
    """Generator that always returns the same code (the worst case for collision handling)."""

    def __init__(self, code: str) -> None:
        self.code = code
        self.calls = 0

    def __call__(self) -> str:
        self.calls += 1
        return self.code


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def session_factory(tmp_path: Path) -> Iterator[sessionmaker[Session]]:
    engine = make_engine(f"sqlite:///{tmp_path / 'links.db'}")
    init_db(engine)
    yield make_session_factory(engine)
    engine.dispose()


@pytest.fixture
def session(session_factory: sessionmaker[Session]) -> Iterator[Session]:
    with session_factory() as s:
        yield s


@pytest.fixture
def client(session_factory: sessionmaker[Session], clock: FakeClock) -> Iterator[TestClient]:
    """Default app: real random generator, fake clock, ``short.test`` is the service's own host."""
    app = create_app(session_factory, clock=clock, own_hosts=(OWN_HOST,))
    with TestClient(app, follow_redirects=False) as c:
        yield c


@pytest.fixture
def make_client(session_factory: sessionmaker[Session], clock: FakeClock):
    """Factory for an app with a specific code generator."""
    clients: list[TestClient] = []

    def _make(generator) -> TestClient:  # noqa: ANN001
        app = create_app(session_factory, code_generator=generator, clock=clock, own_hosts=(OWN_HOST,))
        c = TestClient(app, follow_redirects=False)
        clients.append(c)
        return c

    yield _make
    for c in clients:
        c.close()
