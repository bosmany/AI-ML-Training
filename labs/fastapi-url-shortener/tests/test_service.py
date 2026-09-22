"""Service layer: collisions, expiry, click counting, pagination (no HTTP involved)."""

from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy.orm import Session

from conftest import START, AlwaysSame, FakeClock, SequenceGenerator
from lab import service
from lab.errors import CodeGenerationError, ConflictError, GoneError, NotFoundError, ValidationFailed

URL = "https://example.com/page"


def make(session: Session, **kw) -> service.Link:  # noqa: ANN003
    kw.setdefault("url", URL)
    kw.setdefault("now", START)
    return service.create_link(session, **kw)


def test_create_with_custom_code_stores_the_link(session: Session) -> None:
    link = make(session, custom_code="promo", permanent=True)
    fetched = service.get_link(session, "promo")
    assert (fetched.url, fetched.permanent, fetched.clicks, fetched.expires_at) == (URL, True, 0, None)
    assert fetched.id == link.id


def test_duplicate_custom_code_raises_conflict(session: Session) -> None:
    make(session, custom_code="promo")
    with pytest.raises(ConflictError):
        make(session, custom_code="promo", url="https://other.example/")
    assert service.get_link(session, "promo").url == URL, "the original link must be untouched"


def test_custom_codes_are_case_sensitive(session: Session) -> None:
    make(session, custom_code="Promo")
    make(session, custom_code="promo")  # must not conflict
    assert service.list_links(session, 10, 0)[1] == 2


def test_invalid_url_or_reserved_code_is_rejected_before_anything_is_stored(session: Session) -> None:
    with pytest.raises(ValidationFailed):
        make(session, url="javascript:alert(1)")
    with pytest.raises(ValidationFailed):
        make(session, custom_code="docs")
    assert service.list_links(session, 10, 0)[1] == 0


def test_generated_code_collision_is_retried_until_a_free_code_is_found(session: Session) -> None:
    make(session, custom_code="aaaaaaa")
    gen = SequenceGenerator(["aaaaaaa", "aaaaaaa", "bbbbbbb"])
    link = make(session, generator=gen)
    assert link.code == "bbbbbbb"
    assert gen.calls == 3, "two collisions -> exactly three generator calls"
    assert service.get_link(session, "aaaaaaa").url == URL


def test_gives_up_with_code_generation_error_after_max_attempts(session: Session) -> None:
    make(session, custom_code="aaaaaaa")
    gen = AlwaysSame("aaaaaaa")
    with pytest.raises(CodeGenerationError):
        make(session, generator=gen, max_attempts=4)
    assert gen.calls == 4
    make(session, generator=SequenceGenerator(["ccccccc"]))  # session still usable after the failures


def test_ttl_sets_expiry_relative_to_now_and_none_means_never(session: Session) -> None:
    a = make(session, custom_code="ttl1", ttl_seconds=3600)
    b = make(session, custom_code="ttl2")
    assert a.expires_at == (START + timedelta(hours=1)).replace(tzinfo=None)
    assert b.expires_at is None


def test_follow_counts_each_click(session: Session) -> None:
    make(session, custom_code="count")
    for expected in (1, 2, 3):
        assert service.follow_link(session, "count", START).clicks == expected
    assert service.get_link(session, "count").clicks == 3, "get_link must not count a click"
    with pytest.raises(NotFoundError):
        service.follow_link(session, "nope", START)


def test_expiry_boundary_is_inclusive_and_expired_clicks_are_not_counted(session: Session) -> None:
    make(session, custom_code="short", ttl_seconds=60)
    clock = FakeClock()
    clock.advance(59)
    assert service.follow_link(session, "short", clock()).clicks == 1
    clock.advance(1)  # exactly at expires_at
    with pytest.raises(GoneError):
        service.follow_link(session, "short", clock())
    assert service.get_link(session, "short").clicks == 1, "a 410 must not count as a click"
    forever = make(session, custom_code="forev")
    assert service.is_expired(forever, START + timedelta(days=36500)) is False, "no ttl -> never expires"


def test_delete_removes_the_link_and_a_second_delete_is_not_found(session: Session) -> None:
    make(session, custom_code="gone1")
    service.delete_link(session, "gone1")
    with pytest.raises(NotFoundError):
        service.get_link(session, "gone1")
    with pytest.raises(NotFoundError):
        service.delete_link(session, "gone1")
    make(session, custom_code="gone1")  # the code can be reused once deleted


def test_update_changes_target_but_keeps_code_and_clicks(session: Session) -> None:
    make(session, custom_code="edit1")
    service.follow_link(session, "edit1", START)
    updated = service.update_link(session, "edit1", "https://new.example/x")
    assert (updated.url, updated.code, updated.clicks) == ("https://new.example/x", "edit1", 1)
    with pytest.raises(ValidationFailed):
        service.update_link(session, "edit1", "file:///etc/passwd")
    with pytest.raises(NotFoundError):
        service.update_link(session, "missing", "https://x.example/")


def test_list_pagination_boundaries(session: Session) -> None:
    assert service.list_links(session, 10, 0) == ([], 0), "empty database -> no rows, total 0"
    for i in range(5):
        make(session, custom_code=f"code{i}")
    sizes = []
    for offset in (0, 2, 4, 5, 6):
        items, total = service.list_links(session, 2, offset)
        assert total == 5
        sizes.append(len(items))
    assert sizes == [2, 2, 1, 0, 0]
    assert [x.code for x in service.list_links(session, 3, 1)[0]] == ["code1", "code2", "code3"], "oldest first"

