"""Request / response models (Pydantic v2). PROVIDED."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from lab.models import Link, utc_naive

MAX_TTL_SECONDS = 365 * 24 * 3600


class LinkCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: str
    custom_code: str | None = None
    ttl_seconds: int | None = Field(default=None, gt=0, le=MAX_TTL_SECONDS)
    permanent: bool = False


class LinkUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: str


class LinkOut(BaseModel):
    code: str
    short_url: str
    url: str
    permanent: bool
    created_at: datetime  # UTC
    expires_at: datetime | None  # UTC
    clicks: int
    expired: bool


class LinkPage(BaseModel):
    items: list[LinkOut]
    total: int
    limit: int
    offset: int


def link_to_out(link: Link, base_url: str, now: datetime) -> LinkOut:
    """``base_url`` ends with ``/`` (Starlette's ``request.base_url``)."""
    expired = link.expires_at is not None and utc_naive(now) >= link.expires_at
    return LinkOut(
        code=link.code,
        short_url=f"{base_url}{link.code}",
        url=link.url,
        permanent=link.permanent,
        created_at=link.created_at,
        expires_at=link.expires_at,
        clicks=link.clicks,
        expired=expired,
    )
