"""Request dependencies: settings, current user, role checks (reference solution)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from lab.db import get_session
from lab.errors import AuthenticationError, PermissionDeniedError
from lab.models import User
from lab.security import decode_access_token
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
    if credentials is None:
        raise AuthenticationError("Not authenticated")
    claims = decode_access_token(credentials.credentials, settings)
    try:
        user_id = int(claims["sub"])
    except (TypeError, ValueError) as exc:
        raise AuthenticationError("Invalid token") from exc
    user = await session.get(User, user_id)
    if user is None:
        raise AuthenticationError("User no longer exists")
    return user  # the role comes from the DB row, never from the (client-held) token


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_roles(*roles: str) -> Callable[..., User]:
    """Build a dependency that allows only users whose role is in ``roles`` (else 403)."""

    async def checker(user: CurrentUser) -> User:
        if user.role not in roles:
            raise PermissionDeniedError(f"Requires role: {', '.join(roles)}")
        return user

    return checker
