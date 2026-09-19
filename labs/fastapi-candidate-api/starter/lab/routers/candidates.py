"""Candidate CRUD endpoints (starter)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request, Response  # noqa: F401

from lab import service  # noqa: F401
from lab.deps import SessionDep, require_roles
from lab.events import record_event  # noqa: F401
from lab.models import User
from lab.schemas import CandidateCreate, CandidateOut, CandidatePage, CandidateUpdate, SortKey

MAX_PAGE_SIZE = 100
DEFAULT_PAGE_SIZE = 10

router = APIRouter(prefix="/candidates", tags=["candidates"])

# Writers (create/update) are "recruiter" or "admin"; only "admin" may delete.
WriterDep = Annotated[User, Depends(require_roles("recruiter", "admin"))]
AdminDep = Annotated[User, Depends(require_roles("admin"))]


@router.get("", response_model=CandidatePage)
async def list_candidates(
    session: SessionDep,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = DEFAULT_PAGE_SIZE,
    min_score: Annotated[float | None, Query(ge=0, le=100)] = None,
    city: str | None = None,
    sort: SortKey = "id",
) -> CandidatePage:
    """Public. TODO: call ``service.list_candidates`` and build a ``CandidatePage``
    (``pages = service.page_count(total, page_size)``). Query validation is already declared above."""
    raise NotImplementedError("TODO: list candidates")


@router.get("/{candidate_id}", response_model=CandidateOut)
async def get_candidate(candidate_id: int, session: SessionDep) -> CandidateOut:
    """Public. TODO: ``service.get_candidate`` (raises 404) -> ``CandidateOut``."""
    raise NotImplementedError("TODO: get candidate")


@router.post("", response_model=CandidateOut, status_code=201)
async def create_candidate(
    body: CandidateCreate,
    request: Request,
    background_tasks: BackgroundTasks,
    session: SessionDep,
    user: WriterDep,
) -> CandidateOut:
    """Recruiter/admin only.

    TODO: ``service.create_candidate(session, body.model_dump(), created_by=user.id)``; then
    ``background_tasks.add_task(record_event, request.app.state.events, "candidate.created",
    candidate_id=..., email=...)`` (it runs AFTER the response is sent); return ``CandidateOut``.
    """
    raise NotImplementedError("TODO: create candidate")


@router.patch("/{candidate_id}", response_model=CandidateOut)
async def update_candidate(
    candidate_id: int, body: CandidateUpdate, session: SessionDep, user: WriterDep
) -> CandidateOut:
    """Recruiter/admin only. TODO: ``body.model_dump(exclude_unset=True)`` -> ``service.update_candidate``."""
    raise NotImplementedError("TODO: update candidate")


@router.delete("/{candidate_id}", status_code=204)
async def delete_candidate(candidate_id: int, session: SessionDep, admin: AdminDep) -> Response:
    """Admin only. TODO: ``service.delete_candidate`` then ``Response(status_code=204)``."""
    raise NotImplementedError("TODO: delete candidate")
