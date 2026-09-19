"""Business logic on top of the ORM (reference solution). Functions commit their own writes."""

from __future__ import annotations

import math
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from lab.errors import AuthenticationError, ConflictError, NotFoundError
from lab.models import Candidate, User
from lab.security import hash_password, verify_password

SORT_COLUMNS = {
    "id": Candidate.id.asc(),
    "score": Candidate.score.asc(),
    "-score": Candidate.score.desc(),
    "name": func.lower(Candidate.name).asc(),
    "-name": func.lower(Candidate.name).desc(),
}


def normalize_email(email: str) -> str:
    return email.strip().lower()


# ------------------------------------------------------------------ users
async def register_user(session: AsyncSession, email: str, password: str) -> User:
    email = normalize_email(email)
    existing = await session.scalar(select(User).where(User.email == email))
    if existing is not None:
        raise ConflictError("Email already registered")
    user = User(email=email, hashed_password=hash_password(password), role="recruiter")
    session.add(user)
    try:
        await session.commit()
    except IntegrityError as exc:  # lost a race with a concurrent register
        await session.rollback()
        raise ConflictError("Email already registered") from exc
    return user


async def authenticate(session: AsyncSession, email: str, password: str) -> User:
    user = await session.scalar(select(User).where(User.email == normalize_email(email)))
    # Same error for "no such user" and "wrong password": do not reveal which emails exist.
    if user is None or not verify_password(password, user.hashed_password):
        raise AuthenticationError("Incorrect email or password")
    return user


# ------------------------------------------------------------------ candidates
async def list_candidates(
    session: AsyncSession,
    *,
    page: int,
    page_size: int,
    min_score: float | None = None,
    city: str | None = None,
    sort: str = "id",
) -> tuple[list[Candidate], int]:
    """Return ``(items_for_this_page, total_matching_rows)``. Sorting is stable (ties broken by id)."""
    conditions = []
    if min_score is not None:
        conditions.append(Candidate.score >= min_score)
    if city is not None:
        conditions.append(func.lower(Candidate.city) == city.strip().lower())

    total = await session.scalar(select(func.count()).select_from(Candidate).where(*conditions)) or 0
    stmt = (
        select(Candidate)
        .where(*conditions)
        .order_by(SORT_COLUMNS[sort], Candidate.id.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = list((await session.scalars(stmt)).all())
    return items, total


def page_count(total: int, page_size: int) -> int:
    return math.ceil(total / page_size) if total else 0


async def get_candidate(session: AsyncSession, candidate_id: int) -> Candidate:
    candidate = await session.get(Candidate, candidate_id)
    if candidate is None:
        raise NotFoundError(f"Candidate {candidate_id} not found")
    return candidate


async def _email_taken(session: AsyncSession, email: str, *, exclude_id: int | None = None) -> bool:
    stmt = select(Candidate.id).where(Candidate.email == email)
    if exclude_id is not None:
        stmt = stmt.where(Candidate.id != exclude_id)
    return (await session.scalar(stmt)) is not None


async def create_candidate(session: AsyncSession, data: dict[str, Any], *, created_by: int) -> Candidate:
    data = {**data, "email": normalize_email(data["email"])}
    if await _email_taken(session, data["email"]):
        raise ConflictError("A candidate with this email already exists")
    candidate = Candidate(**data, created_by=created_by)
    session.add(candidate)
    await session.commit()
    return candidate


async def update_candidate(session: AsyncSession, candidate_id: int, changes: dict[str, Any]) -> Candidate:
    """Apply only the keys present in ``changes`` (already ``exclude_unset``)."""
    candidate = await get_candidate(session, candidate_id)
    if "email" in changes:
        changes = {**changes, "email": normalize_email(changes["email"])}
        if await _email_taken(session, changes["email"], exclude_id=candidate_id):
            raise ConflictError("A candidate with this email already exists")
    for field, value in changes.items():
        setattr(candidate, field, value)
    await session.commit()
    return candidate


async def delete_candidate(session: AsyncSession, candidate_id: int) -> None:
    candidate = await get_candidate(session, candidate_id)
    await session.delete(candidate)
    await session.commit()
