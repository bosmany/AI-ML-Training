# Root cause: a write transaction held open across a slow external call

**Cause.** `process_pending()` did `BEGIN IMMEDIATE` (taking SQLite's single write lock) and only committed after
the last job, calling the slow partner API (`enrich`) inside that transaction. For the whole batch, no other
connection could write.

**Why the symptoms.** SQLite allows one writer at a time. `record_event()` waited `BUSY_TIMEOUT_S` (5 s) for the
lock, then raised `database is locked`. The outage length equalled the batch length (jobs x API latency).
A bigger timeout only makes requests hang longer, and WAL mode lets readers proceed during a write but still
allows one writer, so neither addresses the cause. The same pattern on Postgres/MySQL shows up as lock waits,
bloat and blocked migrations.

**Fix.** Keep transactions short and free of I/O: read the pending jobs (no transaction held), call `enrich()` with
no lock, then write each result in its own single-statement transaction (`... WHERE status='pending'` keeps it
idempotent). Trade-off: the batch is no longer all-or-nothing, which is fine because each job is independent.

**Prevention.**
- Rule: never do network I/O or sleeps inside a transaction; measure transaction duration and alert on long ones.
- Test that a second writer can get in while the slow call is in flight (this verifier's probe).
- Set a modest busy timeout and handle `database is locked` explicitly with a metric, instead of retrying blindly.
