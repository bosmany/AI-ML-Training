import json
import os
from datetime import timedelta

import pytest
from helpers import NOW, days_ago, make_backup, names

from lab import (LOCK_NAME, MANIFEST_NAME, FileLock, LockHeldError, Policy, UnsafePathError, retry_with_backoff, run,
                 safe_delete, scan_backups, write_manifest_atomic)


@pytest.fixture
def target(tmp_path):
    d = tmp_path / "backups"
    d.mkdir()
    return d


def fill(target, series="db", n=10):
    return [make_backup(target, f"{series}-2024-06-{30 - i:02d}.tar.gz", days_ago(i)) for i in range(n)]


def test_dry_run_is_the_default_and_touches_nothing(target):
    fill(target)
    before = names(target)
    result = run(target, {"db": Policy(keep_last=3)}, now=NOW)
    assert result.dry_run is True
    assert names(target) == before, "no deletions without dry_run=False"
    assert not (target / MANIFEST_NAME).exists(), "a dry run must not write a manifest either"
    assert [d.backup.name for d in result.to_delete] == [f"db-2024-06-{30 - i:02d}.tar.gz" for i in range(3, 10)]
    assert result.deleted == []


def test_execute_deletes_exactly_what_the_plan_said(target):
    fill(target)
    planned = {d.backup.name for d in run(target, {"db": Policy(keep_last=3)}, now=NOW).to_delete}
    result = run(target, {"db": Policy(keep_last=3)}, now=NOW, dry_run=False)
    assert set(result.deleted) == planned
    assert names(target) == [f"db-2024-06-{d}.tar.gz" for d in (28, 29, 30)]


def test_rerun_is_idempotent(target):
    fill(target)
    run(target, {"db": Policy(keep_last=3, keep_monthly=1)}, now=NOW, dry_run=False)
    after_first = names(target)
    second = run(target, {"db": Policy(keep_last=3, keep_monthly=1)}, now=NOW, dry_run=False)
    assert second.deleted == [] and second.errors == []
    assert names(target) == after_first


def test_series_have_independent_policies_and_series_without_policy_are_untouched(target):
    fill(target, "db", 6)
    fill(target, "logs", 6)
    fill(target, "media", 6)
    result = run(target, {"db": Policy(keep_last=2), "logs": Policy(keep_last=4)}, now=NOW, dry_run=False)
    remaining = names(target)
    assert sum(n.startswith("db-") for n in remaining) == 2
    assert sum(n.startswith("logs-") for n in remaining) == 4
    assert sum(n.startswith("media-") for n in remaining) == 6, "no policy -> hands off"
    assert all("no-policy" in d.reasons for d in result.decisions if d.backup.series == "media")


def test_default_policy_applies_to_series_without_their_own(target):
    fill(target, "media", 6)
    run(target, {}, default=Policy(keep_last=1), now=NOW, dry_run=False)
    assert len(names(target)) == 1


def test_unmanaged_entries_are_never_touched(target, tmp_path):
    fill(target, n=4)
    (target / "README.md").write_text("notes")
    (target / ".hidden-2024").write_text("x")
    outside = tmp_path / "outside.bin"
    outside.write_text("precious")
    (target / "evil-2024-01-01.bin").symlink_to(outside)
    backups, unmanaged = scan_backups(target)
    assert len(backups) == 4
    assert dict(unmanaged) == {"README.md": "no series in name", "evil-2024-01-01.bin": "symlink"}
    run(target, {"db": Policy(keep_last=1), "evil": Policy(keep_last=1)}, now=NOW, dry_run=False)
    assert (target / "README.md").exists() and (target / ".hidden-2024").exists()
    assert (target / "evil-2024-01-01.bin").is_symlink() and outside.read_text() == "precious"


def test_backup_directories_are_deleted_recursively(target):
    make_backup(target, "snap-2024-06-01", days_ago(29), is_dir=True)
    make_backup(target, "snap-2024-06-29", days_ago(1), is_dir=True)
    run(target, {"snap": Policy(keep_last=1)}, now=NOW, dry_run=False)
    assert names(target) == ["snap-2024-06-29"]


def test_manifest_lists_kept_and_deleted_and_lock_is_gone(target):
    fill(target, n=5)
    run(target, {"db": Policy(keep_last=2)}, now=NOW, dry_run=False)
    manifest = json.loads((target / MANIFEST_NAME).read_text())
    assert manifest["generated_at"] == NOW.isoformat()
    assert [k["name"] for k in manifest["kept"]] == ["db-2024-06-30.tar.gz", "db-2024-06-29.tar.gz"]
    assert len(manifest["deleted"]) == 3
    assert not (target / LOCK_NAME).exists(), "lock must be released after the run"


def test_atomic_manifest_write_leaves_old_file_intact_when_replace_fails(tmp_path, monkeypatch):
    path = tmp_path / "m.json"
    path.write_text('{"old": true}')

    def boom(src, dst):
        raise OSError("disk full")

    monkeypatch.setattr(os, "replace", boom)
    with pytest.raises(OSError):
        write_manifest_atomic(path, {"new": True})
    assert json.loads(path.read_text()) == {"old": True}, "readers must never see a half-written manifest"
    assert [p.name for p in tmp_path.iterdir()] == ["m.json"], "the temp file must be cleaned up"


def test_atomic_manifest_write_goes_through_os_replace(tmp_path, monkeypatch):
    calls = []
    real = os.replace
    monkeypatch.setattr(os, "replace", lambda s, d: (calls.append((os.path.basename(s), os.path.basename(d))), real(s, d))[1])
    write_manifest_atomic(tmp_path / "m.json", {"a": 1})
    assert len(calls) == 1 and calls[0][1] == "m.json" and calls[0][0] != "m.json"
    assert json.loads((tmp_path / "m.json").read_text()) == {"a": 1}


def test_lock_prevents_concurrent_runs_and_nothing_is_deleted(target):
    fill(target)
    with FileLock(target / LOCK_NAME):  # "another janitor" is running
        with pytest.raises(LockHeldError, match=str(os.getpid())):
            run(target, {"db": Policy(keep_last=1)}, now=NOW, dry_run=False)
    assert len(names(target)) == 10
    assert (target / LOCK_NAME).exists() is False, "the OTHER holder released it; the loser must not leave one behind"


def test_failed_run_still_releases_the_lock(target):
    fill(target)

    def explode(*_a, **_k):
        raise RuntimeError("bug")

    with pytest.raises(RuntimeError):
        run(target, {"db": Policy(keep_last=1)}, now=NOW, dry_run=False, remove=explode)
    assert not (target / LOCK_NAME).exists()
    run(target, {"db": Policy(keep_last=1)}, now=NOW, dry_run=False)  # and a new run can start


def test_losing_the_lock_race_does_not_delete_the_winners_lock(target):
    lock = FileLock(target / LOCK_NAME)
    with lock:
        with pytest.raises(LockHeldError):
            with FileLock(target / LOCK_NAME):
                pass
        assert (target / LOCK_NAME).exists(), "second acquirer must not unlink the first one's lock on failure"


def test_bad_target_and_naive_now_are_rejected(tmp_path):
    with pytest.raises(NotADirectoryError):
        run(tmp_path / "missing", {"db": Policy(keep_last=1)}, now=NOW)
    (tmp_path / "file").write_text("x")
    with pytest.raises(NotADirectoryError):
        run(tmp_path / "file", {"db": Policy(keep_last=1)}, now=NOW)
    with pytest.raises(ValueError):
        run(tmp_path, {"db": Policy(keep_last=1)}, now=NOW.replace(tzinfo=None))


def test_transient_delete_failures_are_retried_with_backoff_and_jitter(target):
    fill(target, n=3)
    attempts = {"n": 0}
    sleeps: list[float] = []

    def flaky(tgt, path):
        attempts["n"] += 1
        if attempts["n"] <= 2:
            raise OSError("device busy")
        safe_delete(tgt, path)

    result = run(target, {"db": Policy(keep_last=2)}, now=NOW, dry_run=False, remove=flaky,
                 sleep=sleeps.append, rng=lambda: 0.5)
    assert result.errors == [] and len(result.deleted) == 1
    assert sleeps == [0.25, 0.5], "rng()*min(cap, 0.5*2**n) with rng fixed at 0.5"


def test_a_delete_that_keeps_failing_is_reported_and_other_deletes_continue(target):
    fill(target, n=4)
    oldest = "db-2024-06-27.tar.gz"

    def selective(tgt, path):
        if path.name == oldest:
            raise PermissionError("nope")
        safe_delete(tgt, path)

    result = run(target, {"db": Policy(keep_last=1)}, now=NOW, dry_run=False, remove=selective, sleep=lambda s: None)
    assert [n for n, _ in result.errors] == [oldest]
    assert sorted(result.deleted) == ["db-2024-06-28.tar.gz", "db-2024-06-29.tar.gz"]
    manifest = json.loads((target / MANIFEST_NAME).read_text())
    assert manifest["errors"][0]["name"] == oldest
    assert oldest in [k["name"] for k in manifest["kept"]], "a file we failed to delete is still on disk: say so"


def test_unsafe_path_from_remover_is_reported_and_not_retried(target):
    fill(target, n=2)
    sleeps = []

    def refuse(tgt, path):
        raise UnsafePathError("outside")

    result = run(target, {"db": Policy(keep_last=1)}, now=NOW, dry_run=False, remove=refuse, sleep=sleeps.append)
    assert result.unsafe == ["db-2024-06-29.tar.gz"] and sleeps == []


def test_protect_younger_than_spares_a_backup_still_being_written(target):
    make_backup(target, "db-2024-06-30-inprogress.tar", NOW - timedelta(minutes=5))
    fill(target, n=3)
    run(target, {"db": Policy(keep_last=1, protect_younger_than=timedelta(hours=1))}, now=NOW, dry_run=False)
    assert "db-2024-06-30-inprogress.tar" in names(target)


def test_retry_with_backoff_full_jitter_cap_and_limits():
    sleeps: list[float] = []
    n = {"c": 0}

    def fail_thrice():
        n["c"] += 1
        if n["c"] < 4:
            raise OSError("x")
        return "done"

    assert retry_with_backoff(fail_thrice, base=1.0, cap=3.0, sleep=sleeps.append, rng=lambda: 1.0) == "done"
    assert sleeps == [1.0, 2.0, 3.0], "upper bound of the jitter range doubles then hits the cap"
    sleeps.clear()
    n["c"] = 0
    retry_with_backoff(fail_thrice, base=1.0, cap=100.0, sleep=sleeps.append, rng=lambda: 0.0)
    assert sleeps == [0.0, 0.0, 0.0], "rng() == 0 means no delay at all (full jitter)"


def test_retry_with_backoff_gives_up_reraises_last_and_ignores_other_exceptions():
    sleeps: list[float] = []
    calls = {"n": 0}

    def always():
        calls["n"] += 1
        raise OSError(f"fail {calls['n']}")

    with pytest.raises(OSError, match="fail 3"):
        retry_with_backoff(always, attempts=3, sleep=sleeps.append, rng=lambda: 1.0)
    assert len(sleeps) == 2, "no sleep after the final attempt"
    with pytest.raises(KeyError):
        retry_with_backoff(lambda: {}["x"], sleep=sleeps.append)
    assert len(sleeps) == 2, "KeyError is not in retry_on: propagate immediately"
    with pytest.raises(ValueError):
        retry_with_backoff(lambda: 1, attempts=0)
