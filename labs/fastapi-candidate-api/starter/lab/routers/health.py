"""Health endpoint (starter)."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    """TODO: return ``{"status": "ok"}``."""
    raise NotImplementedError("TODO: health")
