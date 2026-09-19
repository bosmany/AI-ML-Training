"""Register / login endpoints (starter)."""

from __future__ import annotations

from fastapi import APIRouter

from lab import service  # noqa: F401
from lab.deps import SessionDep, SettingsDep
from lab.schemas import LoginRequest, RegisterRequest, TokenOut, UserOut
from lab.security import create_access_token  # noqa: F401

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserOut, status_code=201)
async def register(body: RegisterRequest, session: SessionDep) -> UserOut:
    """TODO: ``service.register_user`` then ``UserOut.model_validate(user)``."""
    raise NotImplementedError("TODO: register")


@router.post("/login", response_model=TokenOut)
async def login(body: LoginRequest, session: SessionDep, settings: SettingsDep) -> TokenOut:
    """TODO: ``service.authenticate`` then ``TokenOut(access_token=create_access_token(user.id, user.role, settings))``."""
    raise NotImplementedError("TODO: login")
