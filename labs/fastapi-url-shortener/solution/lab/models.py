"""ORM model. PROVIDED. Note the UNIQUE index on ``code``: the database, not your code, guarantees uniqueness."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import Index, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


def utc_naive(dt: datetime) -> datetime:
    """SQLite stores naive datetimes. We store UTC: aware values are converted, naive ones are assumed UTC."""
    if dt.tzinfo is not None:
        return dt.astimezone(UTC).replace(tzinfo=None)
    return dt


class Link(Base):
    __tablename__ = "links"
    __table_args__ = (Index("ux_links_code", "code", unique=True),)

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(32))
    url: Mapped[str] = mapped_column(String(2048))
    permanent: Mapped[bool] = mapped_column(default=False)  # True -> 301, False -> 302
    created_at: Mapped[datetime]  # naive UTC
    expires_at: Mapped[datetime | None] = mapped_column(default=None)  # naive UTC
    clicks: Mapped[int] = mapped_column(default=0)
