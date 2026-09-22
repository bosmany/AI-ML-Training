"""FastAPI application factory (reference solution)."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator
from datetime import UTC, datetime

from fastapi import Depends, FastAPI, Query, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session, sessionmaker

from lab import service
from lab.codes import generate_code
from lab.errors import install_error_handlers
from lab.schemas import LinkCreate, LinkOut, LinkPage, LinkUpdate, link_to_out

DEFAULT_OWN_HOSTS = ("localhost", "127.0.0.1")


def _utc_now() -> datetime:
    return datetime.now(UTC)


def create_app(
    session_factory: sessionmaker[Session],
    *,
    code_generator: Callable[[], str] = generate_code,
    clock: Callable[[], datetime] = _utc_now,
    own_hosts: Iterable[str] = DEFAULT_OWN_HOSTS,
) -> FastAPI:
    """Build the app. ``code_generator`` and ``clock`` are the test seams (force collisions / move time)."""
    app = FastAPI(title="URL Shortener")
    install_error_handlers(app)
    configured_hosts = tuple(own_hosts)

    def get_session() -> Iterator[Session]:
        with session_factory() as session:
            yield session

    def hosts_for(request: Request) -> set[str]:
        # The configured names plus whatever host this very request used: both would be redirect loops.
        return {*configured_hosts, request.url.hostname or ""}

    @app.post("/links", status_code=201, response_model=LinkOut)
    def create_link(body: LinkCreate, request: Request, session: Session = Depends(get_session)) -> LinkOut:
        now = clock()
        link = service.create_link(
            session,
            url=body.url,
            now=now,
            custom_code=body.custom_code,
            ttl_seconds=body.ttl_seconds,
            permanent=body.permanent,
            generator=code_generator,
            own_hosts=hosts_for(request),
        )
        return link_to_out(link, str(request.base_url), now)

    @app.get("/links", response_model=LinkPage)
    def list_links(
        request: Request,
        limit: int = Query(10, ge=1, le=100),
        offset: int = Query(0, ge=0),
        session: Session = Depends(get_session),
    ) -> LinkPage:
        links, total = service.list_links(session, limit, offset)
        now, base = clock(), str(request.base_url)
        return LinkPage(items=[link_to_out(x, base, now) for x in links], total=total, limit=limit, offset=offset)

    @app.get("/links/{code}", response_model=LinkOut)
    def get_link(code: str, request: Request, session: Session = Depends(get_session)) -> LinkOut:
        return link_to_out(service.get_link(session, code), str(request.base_url), clock())

    @app.put("/links/{code}", response_model=LinkOut)
    def update_link(
        code: str, body: LinkUpdate, request: Request, session: Session = Depends(get_session)
    ) -> LinkOut:
        link = service.update_link(session, code, body.url, hosts_for(request))
        return link_to_out(link, str(request.base_url), clock())

    @app.delete("/links/{code}", status_code=204)
    def delete_link(code: str, session: Session = Depends(get_session)) -> Response:
        service.delete_link(session, code)
        return Response(status_code=204)

    # Declared LAST: "/{code}" would otherwise swallow other single-segment paths.
    @app.get("/{code}", response_class=RedirectResponse, status_code=302)
    def follow(code: str, session: Session = Depends(get_session)) -> RedirectResponse:
        link = service.follow_link(session, code, clock())
        return RedirectResponse(link.url, status_code=301 if link.permanent else 302)

    return app
