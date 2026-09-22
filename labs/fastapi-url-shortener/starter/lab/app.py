"""FastAPI application factory (starter)."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator  # noqa: F401
from datetime import UTC, datetime

from fastapi import Depends, FastAPI, Query, Request, Response  # noqa: F401
from fastapi.responses import RedirectResponse  # noqa: F401
from sqlalchemy.orm import Session, sessionmaker

from lab import service  # noqa: F401
from lab.codes import generate_code
from lab.errors import install_error_handlers  # noqa: F401
from lab.schemas import LinkCreate, LinkOut, LinkPage, LinkUpdate, link_to_out  # noqa: F401

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
    """Build the app. ``code_generator`` and ``clock`` are the test seams (force collisions / move time).

    TODO:
      * ``FastAPI(title=...)`` and ``install_error_handlers(app)``;
      * a dependency ``get_session`` that yields a Session from ``session_factory`` and closes it afterwards;
      * the set of "own hosts" for a request = ``own_hosts`` plus ``request.url.hostname`` (the host the client
        used to reach us): a link to either would be a redirect loop;
      * routes (``link_to_out(link, str(request.base_url), clock())`` builds the response body):
          POST   /links          201, body ``LinkCreate`` -> ``LinkOut``     (pass ``code_generator``, ``clock()``)
          GET    /links          ``limit`` (1..100, default 10) and ``offset`` (>= 0, default 0) -> ``LinkPage``
          GET    /links/{code}   ``LinkOut`` (stats; does NOT count a click)
          PUT    /links/{code}   body ``LinkUpdate`` -> ``LinkOut``
          DELETE /links/{code}   204 with an empty body
          GET    /{code}         redirect to the stored URL: 301 when ``link.permanent`` else 302 (404 / 410 come
                                 from the service errors). Declare this route LAST or it swallows the others.
    """
    raise NotImplementedError("TODO: implement create_app")
