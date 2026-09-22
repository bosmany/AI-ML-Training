# Root cause: the server ignores the Idempotency-Key, so a retry is a new charge

**Cause.** `handle_charge()` never reads the `Idempotency-Key` header the client sends. Every request that
passes validation calls the processor and inserts a ledger row. The client is *supposed* to retry when a
response is lost (timeouts are normal), and it re-sends the same key, but the server has nothing that turns
"same key" into "same charge".

**Why the symptoms look the way they do.**
* Duplicates correlate with slow processor days: slower responses mean more client timeouts, and each timeout
  of a request the server already committed triggers a retry.
* The two ledger rows have different charge ids (each is a fresh insert) but identical customer, amount and
  order, seconds apart (the client's back-off).
* Nothing errors: from the server's point of view both requests were valid.

**Fix.** Make retries safe on the server: store `(customer_id, key)` with a hash of the request under a
primary key and CLAIM it atomically (`BEGIN IMMEDIATE`) before calling the processor. Then: same key + same
body replays the stored response; same key + different body is `409`; a duplicate that arrives while the first is
in flight gets `409` (never a second charge); if the processor fails the claim is released so the retry can
succeed. Everything is in SQLite so keys survive restarts.

Band-aids that fail the verifier: disabling client retries (lost responses become failed orders);
de-duplicating on customer+amount within a time window (blocks legitimate repeat purchases); an in-memory set or
a check-then-insert without an atomic claim (loses races between concurrent duplicates and forgets keys on restart).

**Follow-ups worth writing down.** Expire stale `pending` claims left by a crash between claim and completion;
purge old keys after 24 h; reconcile the ledger against the processor daily.

**Prevention.** The regression tests in `tests/test_regression_idempotency.py` (sequential replay and
concurrent duplicates), a contract test in the checkout client's CI, and an alert on duplicate
(customer, amount, order) tuples in the ledger.
