"""Register / login endpoints (reference solution)."""

from __future__ import annotations

from fastapi import APIRouter

from lab import service
from lab.deps import SessionDep, SettingsDep
from lab.schemas import LoginRequest, RegisterRequest, TokenOut, UserOut
from lab.security import create_access_token

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserOut, status_code=201)
async def register(body: RegisterRequest, session: SessionDep) -> UserOut:
    user = await service.register_user(session, body.email, body.password)
    return UserOut.model_validate(user)


@router.post("/login", response_model=TokenOut)
async def login(body: LoginRequest, session: SessionDep, settings: SettingsDep) -> TokenOut:
    user = await service.authenticate(session, body.email, body.password)
    return TokenOut(access_token=create_access_token(user.id, user.role, settings))
