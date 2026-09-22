# Root cause: shared mutable state that outlives a test, plus a test that needs another test's leftovers

**Cause.** Three independent leaks of state between tests, invisible as long as the tests run in file order:
1. `catalog._STOCK` and `pricing._CONFIG` are module-level dicts that tests mutate (`reserve`, `restock`,
   `configure`) and never restore.
2. `Cart.__init__(self, notes=[])` - a mutable default argument. The list is created once at import time and shared
   by every `Cart()`, so `note()` on one cart shows up on all later carts. This is a real production bug, not just a
   test problem.
3. `test_checkout_reserved_the_stock` asserts a stock level produced by the previous test's checkout: an implicit
   ordering dependency.

**Why the symptoms.** In file order each leak happens to be harmless (the polluting test runs after the ones
that would notice). Any change to order (random order, a subset, a parallel worker, `-k`, a new test inserted)
exposes it, so failures look random and disappear on re-run. `sleep()` and retries treat the symptom.

**Fix.** Give every test pristine state (an autouse fixture that calls `catalog.reset()` / `pricing.reset()`
before and after; or make the state instance-based), use `notes=None` and create the list inside `__init__`, and make
the dependent test do its own setup. Never skip or delete the tests.

**Prevention.**
- Run the suite in random order in CI (pytest-randomly / pytest-random-order) and print the seed so a failure can
  be reproduced; also run each test alone occasionally (`--forked` / per-test selection).
- Lint mutable default arguments (ruff B006); avoid module-level mutable state or expose a `reset()`.
- Treat "passes on re-run" as a bug report, not a fix; quarantine with a ticket, never silently retry.
