# Root cause: connections are leaked on error and early-return paths

**Cause.** `get_order`, `create_order` and `cancel_order` lease a connection with `pool.acquire()` and give it
back with `pool.release()` only at the *end* of the happy path. Three other paths leave the function first:
`get_order` on a missing order (raises `NotFound`), `create_order` on invalid input (validation runs *after*
the acquire and raises `ValidationError`), and `cancel_order` on a shipped order (early `return False`).
Each of those permanently removes one connection from the pool.

**Why the symptoms look the way they do.**
* The database is idle: the leaked connections are open but not running anything; the app is waiting on its own pool.
* It takes minutes, not seconds: only a fraction of requests hit the error paths, and the pool has to be
  drained one leaked connection at a time (5 leaks and it is over).
* It worsens on busy days because more traffic means more not-found and invalid requests.
* A restart rebuilds the pool, so everything is fine again until the next drain.
* `list_orders` was already written with `with pool.connection()` and never leaked, which is why the bug is
  only in some endpoints.

**Fix.** Never pair `acquire()`/`release()` by hand: lease with `with self.pool.connection() as conn:` so the
release is in a `finally`, and do argument validation before leasing. The verifier checks that the pool's
in-use count is 0 after each kind of request (not "eventually"), that errors still reach callers, and that a
6-thread mix against a pool of 4 has zero timeouts.

Band-aids that fail: a bigger pool or a longer timeout (it still leaks, just later); catching every exception
and returning `None` (swallows `NotFound`/`ValidationError`, changing behaviour); fixing only the endpoint you
noticed first.

**Prevention.** `tests/test_regression_pool_leaks.py` (assert `pool.in_use == 0` after every request type);
export pool in-use/wait-time metrics and alert on sustained saturation; lint or review rule: no bare
`acquire()` without a context manager.
