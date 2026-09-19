"""Database wiring (scaffold - provided, do not edit).

``get_session`` is the FastAPI dependency every route uses. Tests replace it with
``app.dependency_overrides[get_session]`` so each test gets a brand-new in-memory database.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from lab.models import Base


def build_engine(url: str) -> AsyncEngine:
    return create_async_engine(url)


def build_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    # expire_on_commit=False: objects stay readable after commit (no implicit lazy load in async code).
    return async_sessionmaker(engine, expire_on_commit=False)


async def init_models(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    """Yield one AsyncSession per request from the app's session factory."""
    factory: async_sessionmaker[AsyncSession] = request.app.state.session_factory
    async with factory() as session:
        yield session
