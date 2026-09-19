"""Application factory (scaffold - provided, do not edit).

Why a factory? Starlette builds its middleware stack on the FIRST request. Exception
handlers or middleware registered after that are silently ignored (``add_middleware``
even raises ``RuntimeError``). Building the app inside ``create_app`` guarantees that
everything is registered before the first request, and gives every test its own
isolated app instance (no shared module-level ``app`` global to leak state).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from lab.db import build_engine, build_session_factory, init_models
from lab.errors import register_exception_handlers
from lab.middleware import add_timing_middleware
from lab.routers import auth, candidates, health
from lab.settings import Settings


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        # Only runs when the app is served for real (uvicorn) or used as ``with TestClient(app)``.
        engine = build_engine(settings.database_url)
        app.state.session_factory = build_session_factory(engine)
        await init_models(engine)
        yield
        await engine.dispose()

    app = FastAPI(title="Candidate Scoring API", version="1.0.0", lifespan=lifespan)
    app.state.settings = settings
    app.state.events = []  # background tasks append here (see lab.events)

    # Order matters: everything below must happen BEFORE the first request is served.
    register_exception_handlers(app)
    add_timing_middleware(app)
    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(candidates.router)
    return app
