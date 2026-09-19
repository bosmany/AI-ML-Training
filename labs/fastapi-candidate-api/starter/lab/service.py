"""Business logic on top of the ORM (starter). Service functions commit their own writes."""

from __future__ import annotations

import math
from typing import Any

from sqlalchemy import func, select  # noqa: F401
from sqlalchemy.exc import IntegrityError  # noqa: F401
from sqlalchemy.ext.asyncio import AsyncSession

from lab.errors import AuthenticationError, ConflictError, NotFoundError  # noqa: F401
from lab.models import Candidate, User
from lab.security import hash_password, verify_password  # noqa: F401

# TODO (list_candidates): map every allowed ``sort`` key to an ORDER BY expression.
#   "id" / "score" / "-score" / "name" / "-name". Name sorting must ignore letter case
#   (``func.lower(Candidate.name)``). Always append ``Candidate.id.asc()`` as a final tie-break so
#   pagination is deterministic when scores are equal.
SORT_COLUMNS: dict[str, Any] = {}


def normalize_email(email: str) -> str:
    """Emails are stored stripped and lower-cased. (Provided.)"""
    return email.strip().lower()


def page_count(total: int, page_size: int) -> int:
    """Number of pages; 0 when there are no rows. (Provided.)"""
    return math.ceil(total / page_size) if total else 0


# ------------------------------------------------------------------ users
async def register_user(session: AsyncSession, email: str, password: str) -> User:
    """Create a user with role "recruiter" (never let the caller pick the role).

    TODO: normalise the email; raise ``ConflictError`` if it exists (also catch ``IntegrityError`` on
    commit for the race between two simultaneous registrations, after ``session.rollback()``);
    store ``hash_password(password)``; commit; return the user.
    """
    raise NotImplementedError("TODO: register_user")


async def authenticate(session: AsyncSession, email: str, password: str) -> User:
    """Return the user for valid credentials, else raise ``AuthenticationError``.

    TODO: look up by normalised email. Unknown email and wrong password must raise the SAME error
    with the SAME message ("Incorrect email or password") so attackers cannot enumerate accounts.
    """
    raise NotImplementedError("TODO: authenticate")


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
    """Return ``(items_for_this_page, total_matching_rows)``.

    TODO: filters combine with AND. ``min_score`` is inclusive (``>=``). ``city`` is a case-insensitive
    exact match. ``total`` is a ``COUNT(*)`` over the FILTERED rows (not the whole table). Order by
    ``SORT_COLUMNS[sort]`` then apply ``offset((page - 1) * page_size).limit(page_size)``.
    """
    raise NotImplementedError("TODO: list_candidates")


async def get_candidate(session: AsyncSession, candidate_id: int) -> Candidate:
    """Return the candidate or raise ``NotFoundError(f"Candidate {candidate_id} not found")``."""
    raise NotImplementedError("TODO: get_candidate")


async def create_candidate(session: AsyncSession, data: dict[str, Any], *, created_by: int) -> Candidate:
    """Insert a candidate. Normalise the email; raise ``ConflictError`` if another candidate has it.

    TODO: set ``created_by``; commit; return the new row (with its generated id).
    """
    raise NotImplementedError("TODO: create_candidate")


async def update_candidate(session: AsyncSession, candidate_id: int, changes: dict[str, Any]) -> Candidate:
    """Apply only the keys present in ``changes`` (the router passes ``model_dump(exclude_unset=True)``).

    TODO: 404 via ``get_candidate``; if ``email`` is changing, normalise it and raise ``ConflictError`` when
    ANOTHER candidate owns it (re-sending the candidate's own email is fine); ``setattr`` each change;
    commit; return the candidate.
    """
    raise NotImplementedError("TODO: update_candidate")


async def delete_candidate(session: AsyncSession, candidate_id: int) -> None:
    """Delete the candidate (404 if missing) and commit."""
    raise NotImplementedError("TODO: delete_candidate")
