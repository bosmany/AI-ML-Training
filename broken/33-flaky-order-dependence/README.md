# 33 - The test suite that fails on Tuesdays

**Category:** CI/CD  |  **Difficulty:** medium  |  **Target time:** 25-40 min

## Symptoms

- CI on the `shop` package goes red about one run in three; re-running the same commit usually turns it green.
  Different tests fail on different runs (`test_default_tax`, `test_initial_apple_stock`, `test_new_cart_has_no_notes`, ...).
- Run the way the team always does on a laptop (`cd app && pytest`), all 12 tests pass.
- A colleague running a single test by name sees `test_checkout_reserved_the_stock` fail, while the full run passes.
- The team "fixed" it twice by adding `sleep()` calls and by pinning a retry-on-failure step; neither helped for long.
- When someone tried shuffling the test order, nearly every run failed.

## What you have

- `app/shop/` - the code under test; `app/tests/` - the suite (12 tests). Run it with `cd app && python -m pytest -q`.
- `verify.py` - runs the suite in normal order, in 20 seeded random orders, in reverse, and each test alone;
  it also runs its own behaviour tests against `shop`. Needs pytest (course venv). No plugins required.

## Your job

1. Find the root cause(s).
2. Fix them without deleting, skipping or xfail-ing tests, and without changing the public API of `shop`.
3. `python verify.py` must exit 0 (`BROKEN_TARGET=solution python verify.py` checks the reference).
4. Fill in `postmortem_template.md` and add a prevention action.

Run with the course venv: `/home/laborant/repos/AI-ML-Training/.fastapi-venv/bin/python verify.py`
