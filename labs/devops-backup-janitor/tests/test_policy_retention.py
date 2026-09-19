from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from helpers import NOW

from lab import Backup, Policy, decide, parse_policy, series_of


def bk(name: str, when: datetime, series: str = "db") -> Backup:
    return Backup(Path(name), name, series, when)


def utc(*a) -> datetime:
    return datetime(*a, tzinfo=timezone.utc)


def kept(decisions) -> list[str]:
    return sorted(d.backup.name for d in decisions if d.keep)


def test_series_of_takes_the_prefix_before_the_date():
    assert series_of("db-prod-2024-03-01.tar.gz") == "db-prod"
    assert series_of("logs-20240301.tgz") == "logs"
    assert series_of("README.md") is None
    assert series_of("2024-03-01.tar") is None


def test_parse_policy_and_its_validation():
    p = parse_policy("last:3, daily:7,monthly:6")
    assert (p.keep_last, p.keep_daily, p.keep_weekly, p.keep_monthly) == (3, 7, 0, 6)
    for bad in ["", "last", "last:x", "yearly:1", "last:1,last:2", "last:-1"]:
        with pytest.raises(ValueError):
            parse_policy(bad)


def test_policy_that_would_delete_everything_is_refused():
    with pytest.raises(ValueError, match="delete ALL"):
        Policy()
    with pytest.raises(ValueError):
        Policy(keep_last=1, protect_younger_than=timedelta(hours=-1))


def test_keep_last_keeps_the_newest_k_regardless_of_input_order():
    backups = [bk(f"db-{i}", utc(2024, 6, i + 1)) for i in (3, 0, 4, 1, 2)]
    assert kept(decide(backups, Policy(keep_last=2), NOW)) == ["db-3", "db-4"]
    assert kept(decide(backups, Policy(keep_last=99), NOW)) == sorted(b.name for b in backups), "K larger than count keeps all"
    assert decide([], Policy(keep_last=1), NOW) == []


def test_keep_daily_keeps_only_the_newest_backup_of_each_day():
    backups = [bk("d1-early", utc(2024, 6, 20, 1)), bk("d1-late", utc(2024, 6, 20, 23)),
               bk("d2", utc(2024, 6, 21, 3)), bk("d3", utc(2024, 6, 22, 3))]
    assert kept(decide(backups, Policy(keep_daily=2), NOW)) == ["d2", "d3"]
    assert kept(decide(backups, Policy(keep_daily=3), NOW)) == ["d1-late", "d2", "d3"], "one per day: early one dies"


def test_keep_daily_counts_days_that_have_backups_not_calendar_days():
    backups = [bk("a", utc(2024, 6, 1)), bk("b", utc(2024, 6, 10)), bk("c", utc(2024, 6, 25))]
    assert kept(decide(backups, Policy(keep_daily=2), NOW)) == ["b", "c"], "gaps must not eat the budget"


def test_day_boundary_is_midnight_utc():
    backups = [bk("before", utc(2024, 6, 20, 23, 59, 59)), bk("after", utc(2024, 6, 21, 0, 0, 0))]
    assert kept(decide(backups, Policy(keep_daily=2), NOW)) == ["after", "before"], "different UTC days"


def test_keep_weekly_uses_iso_weeks_monday_to_sunday():
    backups = [bk("sun", utc(2024, 6, 23, 12)), bk("mon", utc(2024, 6, 24, 12)), bk("tue", utc(2024, 6, 25, 12))]
    # Sun 23rd = week 25; Mon 24th and Tue 25th = week 26 -> newest of week 26 is 'tue'
    assert kept(decide(backups, Policy(keep_weekly=2), NOW)) == ["sun", "tue"]
    assert kept(decide(backups, Policy(keep_weekly=1), NOW)) == ["tue"]


def test_iso_week_across_new_year_uses_iso_year():
    # 2024-12-30 (Mon) is ISO week 1 of 2025, same week as 2025-01-02
    backups = [bk("dec30", utc(2024, 12, 30, 9)), bk("jan02", utc(2025, 1, 2, 9)), bk("dec25", utc(2024, 12, 25, 9))]
    assert kept(decide(backups, Policy(keep_weekly=1), utc(2025, 1, 3))) == ["jan02"]
    assert kept(decide(backups, Policy(keep_weekly=2), utc(2025, 1, 3))) == ["dec25", "jan02"]


def test_keep_monthly_keeps_newest_of_each_month():
    backups = [bk("jan1", utc(2024, 1, 5)), bk("jan2", utc(2024, 1, 28)), bk("feb", utc(2024, 2, 10)),
               bk("mar", utc(2024, 3, 3))]
    assert kept(decide(backups, Policy(keep_monthly=2), NOW)) == ["feb", "mar"]
    assert kept(decide(backups, Policy(keep_monthly=3), NOW)) == ["feb", "jan2", "mar"]


def test_rules_are_ored_together_and_reasons_are_reported():
    backups = [bk(f"d{i}", utc(2024, 6, 30 - i, 6)) for i in range(10)]  # one per day, d0 newest
    decisions = {d.backup.name: d for d in decide(backups, Policy(keep_last=2, keep_daily=3, keep_weekly=2), NOW)}
    assert set(decisions["d0"].reasons) == {"last", "daily", "weekly"}
    assert decisions["d2"].reasons == ("daily",)
    assert decisions["d9"].keep is False and decisions["d9"].reasons == ()


def test_identical_mtimes_are_resolved_deterministically_by_name():
    same = utc(2024, 6, 20, 12)
    backups = [bk("db-a", same), bk("db-b", same), bk("db-c", same)]
    first = kept(decide(backups, Policy(keep_last=1), NOW))
    assert first == ["db-c"] == kept(decide(list(reversed(backups)), Policy(keep_last=1), NOW))


def test_recent_backups_are_protected_with_a_strict_age_boundary():
    pol = Policy(keep_last=1, protect_younger_than=timedelta(hours=2))
    backups = [bk("new", NOW - timedelta(minutes=10)), bk("edge", NOW - timedelta(hours=2)),
               bk("young", NOW - timedelta(hours=1, minutes=59)), bk("old", NOW - timedelta(days=3))]
    assert kept(decide(backups, pol, NOW)) == ["new", "young"], "exactly 2h old is NOT protected; older than that dies"


def test_future_dated_backups_are_never_deleted():
    backups = [bk("db-1", NOW - timedelta(days=5)), bk("db-2", NOW - timedelta(days=4)), bk("future", NOW + timedelta(days=30))]
    decisions = {d.backup.name: d for d in decide(backups, Policy(keep_last=1), NOW)}
    assert decisions["future"].keep, "a mtime in the future (clock skew) is suspicious, not disposable"
