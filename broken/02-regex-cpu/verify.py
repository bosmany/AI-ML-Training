#!/usr/bin/env python3
"""Verifier for 02-regex-cpu.  Usage: python verify.py   (BROKEN_TARGET=solution to check the reference)"""
import os
import re
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "_common"))
from harness import Verifier  # noqa: E402

# The validators as they were before the incident: the reference for accept/reject behaviour.
OLD_USERNAME = re.compile(r"^([a-zA-Z0-9]+[._-]?)+$")
OLD_TAGS = re.compile(r"^([\w-]+,?)*$")

# Inputs an attacker (or a confused user) can send within the length limits. All are invalid.
USERNAME_ATTACKS = ["a" * 40 + "!", "ab" * 20 + "@", "A" * 63 + "#", "a1" * 25 + " x", "user" * 12 + "é",
                    "a." * 24 + "!", "z" * 55 + "?"]
TAG_ATTACKS = ["a" * 50 + "!", "tag-" * 40 + "!", "x" * 200 + " ", "a-b" * 60 + ";", "abc," * 50 + ",,", "é" * 120 + "!"]
LONG_VALID_USERNAMES = ["a" * 64, "ab-" * 21 + "a", "n.a-m_e" * 8 + "xx"]
LONG_VALID_TAGS = ["tag-one," * 30 + "end", "x" * 256, ",".join(["ml"] * 80)[:255]]


def probe_attacks():
    import json
    import signal
    import time
    import validators

    class Slow(Exception):
        pass

    def on_alarm(signum, frame):
        raise Slow()

    signal.signal(signal.SIGALRM, on_alarm)
    rows = []
    for fn, inputs in ((validators.is_valid_username, USERNAME_ATTACKS), (validators.is_valid_tag_list, TAG_ATTACKS)):
        for text in inputs:
            t = time.perf_counter()
            signal.setitimer(signal.ITIMER_REAL, 0.5)
            try:
                result, slow = fn(text), False
            except Slow:
                result, slow = None, True
            finally:
                signal.setitimer(signal.ITIMER_REAL, 0)
            rows.append({"fn": fn.__name__, "n": len(text), "secs": time.perf_counter() - t, "slow": slow, "result": result})
    time.sleep(0.3)  # a "timeout in a thread" band-aid keeps burning CPU after returning
    print(json.dumps({"rows": rows, "cpu": time.process_time()}))


def probe_differential():
    import itertools
    import json
    import random
    import validators

    def old_username(v):
        return isinstance(v, str) and 3 <= len(v) <= 64 and bool(OLD_USERNAME.match(v))

    def old_tags(v):
        return isinstance(v, str) and len(v) <= 256 and bool(OLD_TAGS.match(v))

    rng = random.Random(11)
    alphabet_u = "aZ0._- !@"
    alphabet_t = "aZ0-_, ;é"
    cases = []
    for n in range(0, 5):
        cases += ["".join(p) for p in itertools.product(alphabet_u, repeat=n)]
    for n in range(5, 13):
        cases += ["".join(rng.choice(alphabet_u) for _ in range(n)) for _ in range(250)]
    bad = None
    for s in cases:
        if validators.is_valid_username(s) != old_username(s):
            bad = ["username", s]
            break
    if not bad:
        tcases = []
        for n in range(0, 5):
            tcases += ["".join(p) for p in itertools.product(alphabet_t, repeat=n)]
        for n in range(5, 13):
            tcases += ["".join(rng.choice(alphabet_t) for _ in range(n)) for _ in range(250)]
        for s in tcases:
            if validators.is_valid_tag_list(s) != old_tags(s):
                bad = ["tags", s]
                break
    print(json.dumps({"checked": len(cases), "mismatch": bad}))


def probe_long_valid():
    import json
    import validators
    u = [validators.is_valid_username(s) for s in LONG_VALID_USERNAMES]
    t = [validators.is_valid_tag_list(s) for s in LONG_VALID_TAGS]
    print(json.dumps({"username": u, "tags": t,
                      "too_long": [validators.is_valid_username("a" * 65), validators.is_valid_tag_list("a" * 257)]}))


def main():
    v = Verifier(__file__)
    data, err = v.probe(__file__, "attacks", timeout=25)
    if data is None:
        v.check("adversarial inputs finish quickly", False, err)
    else:
        rows = data["rows"]
        slow = [r for r in rows if r["slow"] or r["secs"] > 0.05]
        v.check("adversarial inputs finish in < 50 ms", not slow,
                "%d of %d slow; worst %.2fs (%s, len %d)" % (len(slow), len(rows), max(r["secs"] for r in rows),
                                                             max(rows, key=lambda r: r["secs"])["fn"],
                                                             max(rows, key=lambda r: r["secs"])["n"]))
        wrong = [r for r in rows if not r["slow"] and r["result"] is not False]
        v.check("adversarial inputs are still rejected (no truncation or guessing)", not wrong,
                "%d wrongly accepted" % len(wrong))
        v.check("no runaway CPU left behind (thread/timeout band-aids)", data["cpu"] < 1.0, "process CPU %.2fs" % data["cpu"])
    d, err = v.probe(__file__, "differential", timeout=25)
    if d is None:
        v.check("accept/reject identical to the old validators", False, err)
    else:
        v.check("accept/reject identical to the old validators on %d+ strings" % d["checked"], d["mismatch"] is None,
                "first mismatch: %r" % (d["mismatch"],))
    d, err = v.probe(__file__, "long_valid", timeout=25)
    if d is None:
        v.check("long valid inputs still accepted", False, err)
    else:
        ok = all(d["username"]) and all(d["tags"]) and not any(d["too_long"])
        v.check("long valid inputs are still accepted, over-long ones rejected", ok, str(d))
    v.pytest()
    v.finish()


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "--probe":
        sys.path.insert(0, os.environ["BROKEN_TARGET_DIR"])
        globals()["probe_" + sys.argv[2].replace("-", "_")]()
    else:
        main()
