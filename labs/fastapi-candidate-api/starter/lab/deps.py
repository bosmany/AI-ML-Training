"""Request dependencies: settings, current user, role checks (starter)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from lab.db import get_session
from lab.errors import AuthenticationError, PermissionDeniedError  # noqa: F401
from lab.models import User
from lab.security import decode_access_token  # noqa: F401
from lab.settings import Settings

# auto_error=False so a missing header goes through OUR handler (envelope + 401) instead of FastAPI's default.
bearer_scheme = HTTPBearer(auto_error=False)


# --------------------------------------------------------------------- scaffold (provided)
def get_settings(request: Request) -> Settings:
    return request.app.state.settings


SessionDep = Annotated[AsyncSession, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


# --------------------------------------------------------------------- your work
async def get_current_user(
    session: SessionDep,
    settings: SettingsDep,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> User:
    """Resolve the bearer token to a ``User`` row.

    TODO: no credentials -> ``AuthenticationError``; ``decode_access_token`` (raises 401 itself);
    ``int(claims["sub"])`` (bad value -> 401); load the user with ``session.get(User, id)`` (missing ->
    401 "user no longer exists"). Return the DB row: authorisation must use ``user.role`` from the
    database, never the ``role`` claim inside the client-held token.
    """
    raise NotImplementedError("TODO: get_current_user")


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_roles(*roles: str) -> Callable[..., User]:
    """Build a dependency that allows only users whose role is in ``roles``."""

    async def checker(user: CurrentUser) -> User:
        """TODO: raise ``PermissionDeniedError`` (403) when ``user.role`` is not in ``roles``, else
        return the user. (401 = "who are you?", 403 = "I know who you are, and no.")"""
        raise NotImplementedError("TODO: role check")

    return checker
