# Lab: Streaming nginx Log Analyzer (CLI)

Build a real command-line tool that reads an nginx access log **as a stream** and reports the top IPs and
paths, the 5xx error rate per hour, p50/p95/p99 request latency and IPs that look like brute-force attackers.
It prints text or JSON and can fail a CI job when the error rate is too high.

## Why it matters in a real job

Log triage is the most common "Python for DevOps" task: an incident is running and you have a 6 GB
`access.log` on a box with 2 GB of RAM. The difference between a script that works in the interview and one
that works in production is exactly what the tests pin: generators instead of `readlines()`, tolerance for
garbage lines (with a count of how many were skipped), correct percentile maths, UTC hour buckets, and a
meaningful exit code so the tool can gate a pipeline.

## Prerequisites (course chapters)

- [Log parsing and text processing](../../devops/do01-log-parsing-text-processing.html)
- [Automation scripts and resilience](../../devops/do03-automation-scripts-resilience.html)
- [Python for DevOps and APIs](../../python/ch07-python-devops-apis.html)
- [Professional Python](../../python/ch06-professional-python.html) (generators, testing)

## Run it

```bash
cd labs/devops-log-analyzer
python -m venv .venv && source .venv/bin/activate    # optional but recommended
pip install -r requirements.txt
pytest -q                        # starter: every test fails until you implement it
LAB_TARGET=solution pytest -q    # maintainers / CI: the reference solution passes
```

Edit only files under `starter/lab/`. Tests do `from lab import ...`; `tests/conftest.py` puts `starter/` (or
`solution/` when `LAB_TARGET=solution`) on `sys.path`. Look at `solution/` only after you have tried.

## Log format

nginx `combined` plus the request time as the last field (`log_format ... '$request_time'`):

```
203.0.113.9 - - [10/Mar/2024:13:55:36 +0000] "GET /a?x=1 HTTP/1.1" 200 512 "-" "curl/8.0" 0.123
```

## What is provided vs what you write

Provided: the dataclasses in `models.py` (including `Report.to_dict`), the argparse definition in `cli.py`.
You write: `parser.py` (regex, `parse_line`, the lazy `iter_entries` generator), `stats.py` (`percentile`,
`BruteForceDetector`), `analyzer.py` (single-pass aggregation), `render.py`, and `main()` in `cli.py`.

## Tasks

1. **Parse one line** - `parse_line` returns a `LogEntry` or `None`; never raises. Strip the query string.
2. **Stream** - `iter_entries` is a generator: one line pulled per entry, blank lines ignored, bad lines counted in `ParseStats.skipped`.
3. **Percentiles** - nearest-rank `percentile`; empty input gives `None`; do not mutate the input.
4. **Brute-force detector** - sliding window over 401/403 responses per IP (rule below).
5. **Analyzer** - top-N (ties alphabetical), 5xx rate overall and per UTC hour, latency, suspects, all in ONE pass.
6. **Render** - text and JSON; JSON on stdout must contain nothing else.
7. **CLI** - `main(argv) -> int`, exit codes 0 / 1 (`--fail-on-error-rate` exceeded) / 2 (bad args, unreadable file, or a non-empty file with zero valid lines).

Window rule: a burst is `threshold` failures whose first-to-last span is **strictly less than** the window.
Five failures at t=0,15,30,45,59s with a 60 s window are flagged; at 0..60s they are not.

## Hints

<details><summary>Regex for the line</summary>

Named groups: `ip`, `ts` (inside `[...]`), `req` (inside the first quotes), `status` (3 digits), `bytes`
(digits or `-`), then two more quoted fields (referrer, user agent) and an optional trailing number.
Use `[^"]*` for quoted fields so user agents with spaces and brackets work.
</details>

<details><summary>Making it lazy</summary>

`for line in lines: ... yield entry` - never `lines = list(lines)`, `readlines()` or `sorted(lines)`.
The tests hand you an iterator that raises if it is consumed further than needed.
</details>

<details><summary>Sliding window without keeping everything</summary>

`collections.deque(maxlen=threshold)` per IP. When it is full and `ts - dq[0] < window`, the IP is a suspect.
</details>

<details><summary>Hour buckets</summary>

`entry.timestamp.astimezone(timezone.utc).strftime("%Y-%m-%dT%H")` - convert first, or +0200 logs land in the wrong hour.
</details>

<details><summary>Catching argparse's SystemExit</summary>

`parse_args` calls `sys.exit(2)` on bad input. Wrap it in `try/except SystemExit as e: return e.code`.
</details>

## Stretch goals

- Replace the list of request times with a t-digest or a fixed-bucket histogram (constant memory) and compare the error.
- Read gzip'd logs (`.gz`) transparently, and tail a live file (`--follow`).
- Add `--since/--until` filters and a `--by-status` breakdown.
- Handle logs that are only roughly chronological (nginx writes on request completion): what breaks in the detector?

## How this comes up in interviews

"Parse this access log and tell me the top 10 IPs" is a classic. Interviewers then push on: *what if the file is
50 GB?* (generators), *what about bad lines?* (skip and count, do not crash), *how do you compute p99?*
(nearest-rank vs interpolation, and why you cannot average percentiles), *how does CI use this?* (exit codes).
Be ready to explain the half-open window edge and why an all-garbage file is an error and not a healthy site.

## What this lab does not cover

- Only the `combined` format plus a trailing `request_time`; custom `log_format`s, JSON logs and IPv6 edge cases are not parsed specially.
- Percentiles keep every request time in memory (a list of floats). It streams the file but is not constant memory.
- The brute-force detector assumes chronological input and looks at status codes only, not usernames or user agents.
- No log rotation, no compression, no real-time follow.
