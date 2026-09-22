"""Business logic on top of the ORM (starter). Functions commit their own writes."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import datetime, timedelta  # noqa: F401

from sqlalchemy import func, select, update  # noqa: F401
from sqlalchemy.exc import IntegrityError  # noqa: F401
from sqlalchemy.orm import Session

from lab.codes import generate_code, validate_custom_code  # noqa: F401
from lab.errors import CodeGenerationError, ConflictError, GoneError, NotFoundError  # noqa: F401
from lab.models import Link, utc_naive  # noqa: F401
from lab.validation import validate_target_url  # noqa: F401

MAX_ATTEMPTS = 5


def is_expired(link: Link, now: datetime) -> bool:
    """True from the very instant ``expires_at`` is reached (``now >= expires_at``); never for ``expires_at is None``.

    TODO: ``now`` may be timezone-aware (the app's clock) while the column is naive UTC: use ``utc_naive``.
    """
    raise NotImplementedError("TODO: implement is_expired")


def _try_insert(session: Session, link: Link) -> bool:
    """Insert and commit. Return False (leaving a CLEAN session) when the unique index rejects the code.

    TODO: ``session.add`` + ``session.commit()``; on ``IntegrityError`` call ``session.rollback()`` and return False.
    Do NOT "SELECT first, INSERT second": two requests can pass the check together. The database decides.
    """
    raise NotImplementedError("TODO: implement _try_insert")


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
    """Validate, then store a new link.

    TODO:
      * validate the URL first (``validate_target_url``), then - if given - the custom code;
      * ``created_at = utc_naive(now)``; ``expires_at = created_at + timedelta(seconds=ttl_seconds)`` or None;
        the new row has ``clicks=0``;
      * custom code: one insert attempt; if the unique index says no -> ``ConflictError``;
      * generated code: call ``generator()`` for EVERY attempt (tests replay a fixed sequence to force
        collisions), retry after a collision, and after ``max_attempts`` failed tries raise ``CodeGenerationError``.
    """
    raise NotImplementedError("TODO: implement create_link")


def get_link(session: Session, code: str) -> Link:
    """The link with this exact code or ``NotFoundError``. Does not count a click."""
    raise NotImplementedError("TODO: implement get_link")


def update_link(session: Session, code: str, url: str, own_hosts: Iterable[str] = ()) -> Link:
    """Change the target URL (validated like on create). Code, clicks and expiry stay as they are."""
    raise NotImplementedError("TODO: implement update_link")


def delete_link(session: Session, code: str) -> None:
    """Remove the link; unknown code -> ``NotFoundError`` (so a second delete is a 404 too)."""
    raise NotImplementedError("TODO: implement delete_link")


def list_links(session: Session, limit: int, offset: int) -> tuple[list[Link], int]:
    """One page, oldest first (order by ``Link.id``), and the total number of links (``func.count``)."""
    raise NotImplementedError("TODO: implement list_links")


def follow_link(session: Session, code: str, now: datetime) -> Link:
    """Resolve a code for a redirect: unknown -> ``NotFoundError``, expired -> ``GoneError``, else count the click.

    TODO: increment with ONE atomic statement ``UPDATE links SET clicks = clicks + 1 WHERE id = ...``
    (``update(Link).where(...).values(clicks=Link.clicks + 1)``), commit, ``session.refresh(link)`` and return it.
    Reading the counter into Python and writing ``clicks + 1`` back loses clicks under concurrency.
    Expired or unknown links must NOT be counted.
    """
    raise NotImplementedError("TODO: implement follow_link")
