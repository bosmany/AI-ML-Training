# Lab: Backup Janitor (retention, atomic writes, locking, safe deletes)

Write the tool that keeps a directory of dated backups from filling the disk - **without** ever deleting the
wrong thing. It applies keep-last / daily / weekly / monthly retention per backup series, runs as a dry run unless
told otherwise, is idempotent, writes its manifest atomically, refuses to run twice at once and refuses to delete
anything outside the target directory.

## Why it matters in a real job

A cleanup script is the most dangerous script in the repo: a wrong path deletes production data, a crash leaves a
half-written state file, two cron runs race each other, and a retry storm hammers a struggling NFS mount. Backup
retention is also a classic "design a policy" interview question. This lab makes you write the guard rails.

## Prerequisites (course chapters)

- [Automation scripts and resilience](../../devops/do03-automation-scripts-resilience.html)
- [Python for DevOps and APIs](../../python/ch07-python-devops-apis.html)
- [OOP, files and errors](../../python/ch05-oop-files-errors.html)
- [Professional Python](../../python/ch06-professional-python.html)

## Run it

```bash
cd labs/devops-backup-janitor
python -m venv .venv && source .venv/bin/activate    # optional but recommended
pip install -r requirements.txt
pytest -q                        # starter: every test fails until you implement it
LAB_TARGET=solution pytest -q    # maintainers / CI: the reference solution passes
```

All tests build their backup directories inside `tmp_path`, set ages with `os.utime`, and inject `now`, `sleep`
and `rng`. Nothing outside `tmp_path` is ever touched, and nothing sleeps.

## What is provided vs what you write

Provided: dataclasses (`Backup`, `Decision`, `RunResult`), exception classes, the bucket-key helpers, the exit-code
constants and the argparse definition. You write `policy.py` (validation, parsing), `retention.py` (`decide`),
`fsops.py` (`safe_delete`, `write_manifest_atomic`, `FileLock`), `retry.py`, `janitor.py` (`scan_backups`, `run`) and `main()`.

## Naming and semantics

Backups are files or directories named `<series>-<year>...`, e.g. `db-prod-2024-06-30.tar.gz` (series `db-prod`).
**Age comes from mtime, in UTC**, not from the name.

- `keep_last=N`: the N newest.
- `keep_daily=N`: the newest backup of each of the N most recent *days that have a backup*. Same for ISO weeks (`keep_weekly`) and months.
- Rules are OR-ed; a policy where every rule is 0 is rejected (it would delete everything).
- Backups younger than `protect_younger_than` (still being written) and backups dated in the future are never deleted.
- Series with no policy (and no default) are left alone. Files that do not match the pattern, dot-files and symlinks are never touched.

Exit codes: `0` ok / dry run, `1` some deletions failed, `2` usage error, `3` another run holds the lock, `4` an unsafe path was refused.

## Tasks

1. `Policy` validation, `series_of`, `parse_policy`.
2. `decide`: the retention algorithm (pure function, no filesystem). Watch the ISO-week year boundary and same-mtime ties.
3. `safe_delete`: refuse `..` traversal, symlinks (even ones pointing inside), paths through symlinked directories and the target itself.
4. `write_manifest_atomic`: temp file in the same directory, fsync, `os.replace`; clean up on failure.
5. `FileLock` with `O_CREAT | O_EXCL`; a loser must not remove the winner's lock.
6. `retry_with_backoff`: exponential, capped, full jitter, injectable `sleep` and `rng`.
7. `scan_backups` and `run`: dry run by default, lock, retry deletes, keep going after failures, manifest.
8. `main`: options, exit codes, dry run unless `--execute`.

## Hints

<details><summary>Bucketing</summary>

Sort newest first. For daily: keep a `seen` set of `(y, m, d)`; the first backup you meet in an unseen day is
the newest of that day; stop when `len(seen) == N`. Weekly uses `isocalendar()` (its **ISO year**, not
`.year`); 2024-12-30 belongs to week 1 of 2025.
</details>

<details><summary>Why resolve() and not string checks</summary>

`str(path).startswith(str(target))` is fooled by `/backups-evil` and by `..`. `Path.resolve()` collapses `..` and
follows symlinks; then `resolved.is_relative_to(target.resolve())`. Also refuse when it equals the target.
</details>

<details><summary>Atomic write</summary>

`os.replace` is atomic only within one filesystem, so the temp file lives next to the destination:
`path.with_name(path.name + ".tmp-" + str(os.getpid()))`. `flush()` + `os.fsync()` before replacing.
</details>

<details><summary>The lock</summary>

`os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)` fails with `FileExistsError` if the file exists - one atomic
system call, unlike `if not exists(): create()`. Write your pid into it to help humans debug a stale lock.
</details>

<details><summary>Full jitter</summary>

`sleep(rng() * min(cap, base * 2**n))`. Without jitter every client that failed together retries together.
</details>

## Stretch goals

- Stale-lock detection: check whether the pid in the lock still exists (`os.kill(pid, 0)`), and think about pid reuse.
- Take the lock with `fcntl.flock` so the kernel drops it when the process dies; compare with the lock-file approach.
- `--verify` mode that checks a checksum sidecar before counting a file as a valid backup.
- A "never delete the last good backup" rule when the newest backup is empty or tiny.
- Time zones: make the daily boundary configurable (a backup at 23:30 local is "tomorrow" in UTC).

## How this comes up in interviews

"Write a script that deletes backups older than 30 days" -> *what if the clock is wrong? what if the path is a
symlink? what if it runs twice? what if it dies half-way? how do you test it without waiting 30 days?* Also the
policy question: why grandfather-father-son (daily/weekly/monthly) beats "delete older than N days", and why the
tool must be dry-run by default.

## What this lab does not cover

- Only local filesystems: no S3 lifecycle rules, no NFS/SMB semantics, no object versioning or object lock.
- `O_EXCL` lock files can go stale after a crash (you are told how to clear one, not automatically); `fcntl`-style locks are a stretch goal.
- `safe_delete` checks then deletes; a hostile local user swapping directories in that gap (TOCTOU) is not defended against (`openat`/`dir_fd` APIs would be).
- No verification that backups are restorable - retention only decides which files to keep, which is not the same as having backups.
- No cross-process concurrency test with real processes; the lock is tested deterministically.
