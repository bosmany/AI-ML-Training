import os

import pytest
from helpers import NOW, days_ago, make_backup, names

from lab import (EXIT_DELETE_FAILED, EXIT_LOCKED, EXIT_OK, EXIT_UNSAFE, EXIT_USAGE, LOCK_NAME, FileLock,
                 UnsafePathError, main, safe_delete)


@pytest.fixture
def target(tmp_path):
    d = tmp_path / "backups"
    d.mkdir()
    return d


@pytest.fixture
def outside(tmp_path):
    f = tmp_path / "outside.txt"
    f.write_text("precious")
    return f


def test_safe_delete_removes_a_normal_backup_file_and_tree(target):
    f = make_backup(target, "db-2024-06-01.tar", days_ago(1))
    d = make_backup(target, "snap-2024-06-01", days_ago(1), is_dir=True)
    safe_delete(target, f)
    safe_delete(target, d)
    assert names(target) == []


def test_dotdot_traversal_is_refused(target, outside):
    sneaky = target / ".." / "outside.txt"
    with pytest.raises(UnsafePathError):
        safe_delete(target, sneaky)
    assert outside.read_text() == "precious"
    with pytest.raises(UnsafePathError):
        safe_delete(target, target / "sub" / ".." / ".." / "outside.txt")


def test_symlink_pointing_outside_is_refused_and_destination_survives(target, outside, tmp_path):
    link = target / "db-2024-06-01.tar"
    link.symlink_to(outside)
    with pytest.raises(UnsafePathError):
        safe_delete(target, link)
    assert outside.read_text() == "precious" and link.is_symlink()
    outdir = tmp_path / "elsewhere"
    outdir.mkdir()
    (outdir / "keep.txt").write_text("k")
    dirlink = target / "snap-2024-06-01"
    dirlink.symlink_to(outdir, target_is_directory=True)
    with pytest.raises(UnsafePathError):
        safe_delete(target, dirlink)
    with pytest.raises(UnsafePathError):
        safe_delete(target, dirlink / "keep.txt")  # path THROUGH a symlinked directory
    assert (outdir / "keep.txt").read_text() == "k"


def test_symlink_pointing_inside_the_target_is_refused_and_the_real_file_survives(target):
    real = make_backup(target, "db-2024-06-01.tar", days_ago(5))
    link = target / "db-2024-06-02.tar"
    link.symlink_to(real)
    with pytest.raises(UnsafePathError):
        safe_delete(target, link)
    assert real.exists() and link.is_symlink(), "deleting 'through' a link would destroy the real backup"


def test_the_target_directory_itself_and_its_parents_can_never_be_deleted(target):
    for victim in (target, target.parent, target / "."):
        with pytest.raises(UnsafePathError):
            safe_delete(target, victim)
    assert target.is_dir()


def test_safe_delete_works_when_target_is_reached_through_a_symlink(tmp_path):
    real = tmp_path / "real"
    real.mkdir()
    alias = tmp_path / "alias"
    alias.symlink_to(real, target_is_directory=True)
    f = make_backup(real, "db-2024-06-01.tar", days_ago(1))
    safe_delete(alias, alias / f.name)
    assert names(real) == [], "a symlinked TARGET is fine; only escaping it is not"


def cli(target, *extra, **kw):
    return main([str(target), "--now", NOW.isoformat(), *extra], **kw)


def fill(target, n=6):
    for i in range(n):
        make_backup(target, f"db-2024-06-{30 - i:02d}.tar", days_ago(i))


def test_cli_is_a_dry_run_unless_execute_is_given(target, capsys):
    fill(target)
    assert cli(target, "--keep-last", "2") == EXIT_OK
    out = capsys.readouterr().out
    assert "DRY RUN" in out and "would delete 4" in out and "db-2024-06-25.tar" in out
    assert len(names(target)) == 6
    assert cli(target, "--keep-last", "2", "--execute") == EXIT_OK
    assert len(names(target)) == 2 and "deleted 4" in capsys.readouterr().out


def test_cli_series_option_overrides_the_default(target):
    fill(target)
    for i in range(6):
        make_backup(target, f"logs-2024-06-{30 - i:02d}.tar", days_ago(i))
    assert cli(target, "--keep-last", "5", "--series", "logs=last:1", "--execute") == EXIT_OK
    left = names(target)
    assert sum(n.startswith("db-") for n in left) == 5 and sum(n.startswith("logs-") for n in left) == 1


def test_cli_usage_errors_exit_2_and_delete_nothing(target, tmp_path, capsys):
    fill(target)
    assert cli(target) == EXIT_USAGE, "no policy given: refuse to guess one"
    assert cli(target, "--keep-last", "-1") == EXIT_USAGE
    assert cli(target, "--series", "db") == EXIT_USAGE
    assert cli(target, "--series", "db=yearly:3") == EXIT_USAGE
    assert cli(tmp_path / "nope", "--keep-last", "1") == EXIT_USAGE
    assert main([str(target), "--keep-last", "1", "--now", "not-a-date"]) == EXIT_USAGE
    assert main([]) == EXIT_USAGE
    assert len(names(target)) == 6
    assert "error" in capsys.readouterr().err


def test_cli_returns_3_when_another_run_holds_the_lock(target, capsys):
    fill(target)
    with FileLock(target / LOCK_NAME):
        assert cli(target, "--keep-last", "1", "--execute") == EXIT_LOCKED
    assert len(names(target)) == 6 and "held" in capsys.readouterr().err


def test_cli_exit_codes_for_failed_and_unsafe_deletions(target, monkeypatch):
    fill(target)

    def broken(tgt, path):
        raise OSError("io error")

    monkeypatch.setattr("lab.janitor.safe_delete", broken)
    assert cli(target, "--keep-last", "5", "--execute", sleep=lambda s: None, rng=lambda: 0.0) == EXIT_DELETE_FAILED

    def unsafe(tgt, path):
        raise UnsafePathError("escape")

    monkeypatch.setattr("lab.janitor.safe_delete", unsafe)
    assert cli(target, "--keep-last", "5", "--execute") == EXIT_UNSAFE
