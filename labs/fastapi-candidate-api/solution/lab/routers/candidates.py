"""Candidate CRUD endpoints (reference solution)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request, Response

from lab import service
from lab.deps import SessionDep, require_roles
from lab.events import record_event
from lab.models import User
from lab.schemas import CandidateCreate, CandidateOut, CandidatePage, CandidateUpdate, SortKey

MAX_PAGE_SIZE = 100
DEFAULT_PAGE_SIZE = 10

router = APIRouter(prefix="/candidates", tags=["candidates"])

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
    items, total = await service.list_candidates(
        session, page=page, page_size=page_size, min_score=min_score, city=city, sort=sort
    )
    return CandidatePage(
        items=[CandidateOut.model_validate(c) for c in items],
        total=total,
        page=page,
        page_size=page_size,
        pages=service.page_count(total, page_size),
    )


@router.get("/{candidate_id}", response_model=CandidateOut)
async def get_candidate(candidate_id: int, session: SessionDep) -> CandidateOut:
    return CandidateOut.model_validate(await service.get_candidate(session, candidate_id))


@router.post("", response_model=CandidateOut, status_code=201)
async def create_candidate(
    body: CandidateCreate,
    request: Request,
    background_tasks: BackgroundTasks,
    session: SessionDep,
    user: WriterDep,
) -> CandidateOut:
    candidate = await service.create_candidate(session, body.model_dump(), created_by=user.id)
    # Runs AFTER the response is sent; the client never waits for it.
    background_tasks.add_task(
        record_event, request.app.state.events, "candidate.created",
        candidate_id=candidate.id, email=candidate.email,
    )
    return CandidateOut.model_validate(candidate)


@router.patch("/{candidate_id}", response_model=CandidateOut)
async def update_candidate(
    candidate_id: int, body: CandidateUpdate, session: SessionDep, user: WriterDep
) -> CandidateOut:
    changes = body.model_dump(exclude_unset=True)  # only what the client actually sent
    return CandidateOut.model_validate(await service.update_candidate(session, candidate_id, changes))


@router.delete("/{candidate_id}", status_code=204)
async def delete_candidate(candidate_id: int, session: SessionDep, admin: AdminDep) -> Response:
    await service.delete_candidate(session, candidate_id)
    return Response(status_code=204)
