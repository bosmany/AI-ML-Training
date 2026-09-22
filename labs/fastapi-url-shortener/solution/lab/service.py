"""Business logic on top of the ORM (reference solution). Functions commit their own writes."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import datetime, timedelta

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from lab.codes import generate_code, validate_custom_code
from lab.errors import CodeGenerationError, ConflictError, GoneError, NotFoundError
from lab.models import Link, utc_naive
from lab.validation import validate_target_url

MAX_ATTEMPTS = 5


def is_expired(link: Link, now: datetime) -> bool:
    """A link is expired from the instant ``expires_at`` is reached (``now >= expires_at``)."""
    return link.expires_at is not None and utc_naive(now) >= link.expires_at


def _try_insert(session: Session, link: Link) -> bool:
    """Insert and commit; False (with a clean session) when the unique index on ``code`` rejects it."""
    session.add(link)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        return False
    return True


def create_link(
    session: Session,
    *,
    url: str,
    now: datetime,
    custom_code: str | None = None,
    ttl_seconds: int | None = None,
    permanent: bool = False,
    generator: Callable[[], str] = generate_code,
    own_hosts: Iterable[str] = (),
    max_attempts: int = MAX_ATTEMPTS,
) -> Link:
    target = validate_target_url(url, own_hosts)
    created = utc_naive(now)
    expires = created + timedelta(seconds=ttl_seconds) if ttl_seconds is not None else None

    def build(code: str) -> Link:
        return Link(code=code, url=target, permanent=permanent, created_at=created, expires_at=expires, clicks=0)

    if custom_code is not None:
        link = build(validate_custom_code(custom_code))
        if not _try_insert(session, link):
            raise ConflictError(f"custom_code '{custom_code}' is already taken")
        return link

    for _ in range(max_attempts):
        link = build(generator())
        if _try_insert(session, link):
            return link
    raise CodeGenerationError(f"could not find a free code after {max_attempts} attempts")


def get_link(session: Session, code: str) -> Link:
    link = session.scalar(select(Link).where(Link.code == code))
    if link is None:
        raise NotFoundError(f"unknown short code '{code}'")
    return link


def update_link(session: Session, code: str, url: str, own_hosts: Iterable[str] = ()) -> Link:
    link = get_link(session, code)
    link.url = validate_target_url(url, own_hosts)
    session.commit()
    return link


def delete_link(session: Session, code: str) -> None:
    session.delete(get_link(session, code))
    session.commit()


def list_links(session: Session, limit: int, offset: int) -> tuple[list[Link], int]:
    """One page (oldest first, by id) plus the total number of links."""
    total = session.scalar(select(func.count()).select_from(Link)) or 0
    items = session.scalars(select(Link).order_by(Link.id).limit(limit).offset(offset)).all()
    return list(items), total


def follow_link(session: Session, code: str, now: datetime) -> Link:
    """Resolve a code for a redirect: 404 if unknown, 410 if expired, otherwise count the click."""
    link = get_link(session, code)
    if is_expired(link, now):
        raise GoneError(f"link '{code}' has expired")
    # One atomic UPDATE (clicks = clicks + 1): read-modify-write in Python would lose clicks under concurrency.
    session.execute(update(Link).where(Link.id == link.id).values(clicks=Link.clicks + 1))
    session.commit()
    session.refresh(link)
    return link
