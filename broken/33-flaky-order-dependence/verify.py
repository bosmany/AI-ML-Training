#!/usr/bin/env python3
"""Verifier for broken/33-flaky-order-dependence.  Usage: python verify.py   (BROKEN_TARGET=solution for the reference)

Run it with a Python that has pytest (the course venv). No third-party plugin: a tiny reordering plugin is written
to a temp dir and loaded with `-p`. Everything is deterministic (fixed seeds), nothing touches the repo.

  1. the suite is green in its normal order and none of the original tests were deleted/skipped/xfailed
  2. it stays green in 20 seeded random orders and in reverse order
  3. every test passes when run completely alone (no hidden reliance on another test's leftovers)
  4. behaviour tests written by the verifier (in isolation) still pass: the shop API was not broken
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
TARGET = HERE / ("solution" if os.environ.get("BROKEN_TARGET") == "solution" else "app")
checks = []
SEEDS = list(range(20))
ORIGINAL = {
    "tests/test_cart.py::test_new_cart_has_no_notes", "tests/test_cart.py::test_add_note",
    "tests/test_cart.py::test_checkout_total_includes_tax", "tests/test_cart.py::test_checkout_reserved_the_stock",
    "tests/test_catalog.py::test_initial_apple_stock", "tests/test_catalog.py::test_reserve_reduces_stock",
    "tests/test_catalog.py::test_reserve_out_of_stock_raises", "tests/test_catalog.py::test_restock_adds_units",
    "tests/test_pricing.py::test_default_tax", "tests/test_pricing.py::test_default_currency",
    "tests/test_pricing.py::test_zero_tax_when_configured", "tests/test_pricing.py::test_currency_can_change",
}

PLUGIN = '''
import os, random, pytest

@pytest.hookimpl(wrapper=True)
def pytest_collection_modifyitems(session, config, items):
    result = yield                      # after every other plugin/conftest had its say
    mode = os.environ.get("ORDER_MODE", "")
    if mode:
        items.sort(key=lambda i: i.nodeid)  # canonical base order, independent of file/conftest tricks
    if mode.startswith("seed:"):
        random.Random(int(mode[5:])).shuffle(items)
    elif mode == "reverse":
        items.reverse()
    return result
'''

HIDDEN = '''
import pytest
from shop import catalog, pricing
from shop.cart import Cart

def test_carts_do_not_share_notes():
    a = Cart(); a.note("fragile")
    assert Cart().notes == [] and Cart().notes is not a.notes

def test_explicit_notes_are_used():
    assert Cart(notes=["x"]).notes == ["x"]

def test_subtotal_and_checkout():
    c = Cart(); c.add("apple", 2); c.add("pear")
    assert c.subtotal() == 350
    assert c.checkout() == (420, "USD")
    assert catalog.stock("apple") == 8 and catalog.stock("pear") == 3

def test_checkout_out_of_stock_raises():
    c = Cart(); c.add("fig", 1)
    with pytest.raises(catalog.OutOfStock):
        c.checkout()

def test_configure_changes_tax_and_currency():
    pricing.configure(tax_rate=0.10, currency="EUR")
    assert pricing.with_tax(1000) == 1100 and pricing.currency() == "EUR"

def test_restock():
    catalog.restock("fig", 4)
    assert catalog.stock("fig") == 4
'''


def check(name, ok, detail=""):
    checks.append({"name": name, "ok": bool(ok), "detail": detail})
    return bool(ok)


def finish():
    fixed = all(c["ok"] for c in checks) and bool(checks)
    score = 100 if fixed else min(99, round(100 * sum(c["ok"] for c in checks) / max(1, len(checks))))
    print(json.dumps({"fixed": fixed, "checks": checks, "score": score}, indent=2))
    sys.exit(0 if fixed else 1)


def run(cwd, extra_args, tmp, tag, mode="", pythonpath=()):
    xml = tmp / f"{tag}.xml"
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", ORDER_MODE=mode,
               PYTHONPATH=os.pathsep.join([str(tmp / "plugin"), *map(str, pythonpath)]))
    cmd = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-p", "order_shuffle",
           f"--junitxml={xml}", *extra_args]
    proc = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True, timeout=50)
    res = {"rc": proc.returncode, "passed": [], "failed": [], "skipped": []}
    if xml.exists():
        for tc in ET.parse(xml).getroot().iter("testcase"):
            nodeid = tc.get("classname", "").replace(".", "/") + ".py::" + tc.get("name", "")
            kids = {c.tag for c in tc}
            bucket = "failed" if kids & {"failure", "error"} else "skipped" if "skipped" in kids else "passed"
            res[bucket].append(nodeid)
    return res


def main():
    try:
        import pytest  # noqa: F401
    except ImportError:
        print(json.dumps({"fixed": False, "checks": [{"name": "pytest available", "ok": False,
              "detail": "run with the course venv python (has pytest)"}], "score": 0}))
        sys.exit(2)
    tmp = Path(tempfile.mkdtemp(prefix="broken33-"))
    try:
        (tmp / "plugin").mkdir()
        (tmp / "plugin" / "order_shuffle.py").write_text(PLUGIN)
        work = tmp / "work"
        shutil.copytree(TARGET, work, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"))

        base = run(work, [], tmp, "base")
        present = set(base["passed"] + base["failed"] + base["skipped"])
        check("suite is green in its normal order", base["rc"] == 0 and not base["failed"],
              f"passed={len(base['passed'])} failed={base['failed']}")
        missing = sorted(ORIGINAL - present)
        check("no original test was deleted, skipped or xfailed",
              not missing and not base["skipped"], f"missing={missing} skipped={base['skipped']}")

        bad_seeds = {}
        for seed in SEEDS:
            r = run(work, [], tmp, f"s{seed}", mode=f"seed:{seed}")
            if r["rc"] != 0 or r["failed"] or len(r["passed"]) < len(ORIGINAL):
                bad_seeds[seed] = r["failed"][:3]
        check(f"green in all {len(SEEDS)} shuffled orders (seeds 0-{SEEDS[-1]})", not bad_seeds,
              f"{len(bad_seeds)} failing seeds, e.g. {dict(list(bad_seeds.items())[:2])}" if bad_seeds else "")
        r = run(work, [], tmp, "rev", mode="reverse")
        check("green in reverse order", r["rc"] == 0 and not r["failed"], str(r["failed"][:3]))

        alone_fail = []
        for nodeid in sorted(ORIGINAL):
            r = run(work, [nodeid], tmp, "alone")
            if r["rc"] != 0 or nodeid not in r["passed"]:
                alone_fail.append(nodeid)
        check("every test passes when run completely alone", not alone_fail, str(alone_fail))

        hidden = tmp / "hidden"
        hidden.mkdir()
        (hidden / "pytest.ini").write_text("[pytest]\n")
        (hidden / "test_behaviour.py").write_text(HIDDEN)
        names = [l.split("(")[0][4:] for l in HIDDEN.splitlines() if l.startswith("def test_")]
        hid_fail = []
        for n in names:
            r = run(hidden, [f"test_behaviour.py::{n}"], tmp, "hid", pythonpath=[work])
            if r["rc"] != 0 or not r["passed"]:
                hid_fail.append(n)
        check("shop behaviour is preserved (verifier's own tests, each in a fresh process)", not hid_fail,
              str(hid_fail))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    finish()


if __name__ == "__main__":
    main()
