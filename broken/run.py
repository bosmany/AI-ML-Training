#!/usr/bin/env python3
"""Run one Broken-System Lab and score it.

    python broken/run.py 01                      # verify your app/ (make broken ID=01)
    python broken/run.py 01 --hints 1,2 --minutes 35
    BROKEN_TARGET=solution python broken/run.py 01   # verify the reference solution

Score = 100 - hint costs (L1 10, L2 20, L3 30) - time penalty (1 point per 3 minutes after the first 20, max 20)
        + 10 for a prevention action (a passing app/tests/test_regression_*.py, or a filled
          'prevent'/'detect' action item in postmortem.md).
Success = (a) verify.py exits 0 (fault fixed, behaviour preserved) and (b) postmortem.md has a root-cause section.
Hints and minutes are self-reported (env HINTS / MINUTES also work): the point is honest practice, not a leaderboard.
"""
import argparse
import glob
import json
import math
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
TEMPLATE_HINT = "One or two sentences: the mechanism, not the symptom."


def find_scenario(num):
    num = num.zfill(2)
    hits = sorted(glob.glob(os.path.join(HERE, num + "-*", "verify.py")))
    return os.path.dirname(hits[0]) if hits else None


def parse_json(text):
    i = text.find("{")
    if i < 0:
        return None
    try:
        return json.JSONDecoder().raw_decode(text[i:])[0]
    except ValueError:
        return None


def section(md, title):
    m = re.search(r"^##\s+%s[^\n]*\n(.*?)(?=^##\s|\Z)" % re.escape(title), md, re.S | re.M | re.I)
    return m.group(1) if m else ""


def rca_present(folder):
    path = os.path.join(folder, "postmortem.md")
    if not os.path.isfile(path):
        return False, "postmortem.md not found (copy postmortem_template.md to postmortem.md and fill it in)"
    text = section(open(path, encoding="utf-8").read(), "Root cause").replace(TEMPLATE_HINT, "")
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S).strip()
    if len(text) < 40:
        return False, "postmortem.md: the 'Root cause' section is empty or too short (need the mechanism, 40+ characters)"
    return True, "postmortem.md has a root-cause section"


def prevention(folder):
    tests = sorted(glob.glob(os.path.join(folder, "app", "tests", "test_regression*.py")))
    if tests:
        env = dict(os.environ, PYTHONPATH=os.path.join(folder, "app"))
        p = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"] + tests,
                           cwd=os.path.join(folder, "app"), env=env, capture_output=True, text=True, timeout=120)
        if p.returncode == 0:
            return True, "regression test(s) pass: " + ", ".join(os.path.basename(t) for t in tests)
    path = os.path.join(folder, "postmortem.md")
    if os.path.isfile(path):
        for row in section(open(path, encoding="utf-8").read(), "Action items").splitlines():
            cells = [c.strip() for c in row.strip().strip("|").split("|")]
            if len(cells) >= 2 and len(cells[0]) >= 10 and re.search(r"prevent|detect", cells[1], re.I) \
                    and not re.search(r"^-+$|^action$", cells[0], re.I):
                return True, "postmortem.md lists a prevent/detect action item"
    return False, "no prevention action found (add app/tests/test_regression_*.py or a prevent/detect action item)"


def hint_cost(folder, levels):
    hints = json.load(open(os.path.join(folder, "hints.json")))["hints"]
    by_level = {h["level"]: h.get("penalty", h.get("cost", 0)) for h in hints}
    return sum(by_level.get(l, 0) for l in levels)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("id", help="scenario number, e.g. 01")
    ap.add_argument("--hints", default=os.environ.get("HINTS", ""), help="hint levels you used, e.g. 1,2")
    ap.add_argument("--minutes", type=float, default=float(os.environ.get("MINUTES") or 0), help="minutes spent")
    a = ap.parse_args()
    folder = find_scenario(a.id)
    if not folder:
        cat = os.path.join(HERE, "catalog.json")
        planned = ""
        try:
            for s in json.load(open(cat))["scenarios"]:
                if s["num"] == a.id.zfill(2):
                    planned = " ('%s' is %s in catalog.json)" % (s["title"], s["status"])
        except OSError:
            pass
        print("No runnable lab for ID=%s%s. Available labs are the folders under broken/." % (a.id, planned))
        return 3
    target = os.environ.get("BROKEN_TARGET", "app")
    p = subprocess.run([sys.executable, os.path.join(folder, "verify.py")], cwd=folder, capture_output=True, text=True)
    res = parse_json(p.stdout)
    name = os.path.basename(folder)
    print("== %s   (target: %s)" % (name, target))
    if res is None:
        print("verify.py did not produce a result:\n" + (p.stdout + p.stderr)[-800:])
        return 2
    for c in res.get("checks", []):
        print("  [%s] %s%s" % ("PASS" if c["ok"] else "FAIL", c["name"], ("  -- " + c["detail"]) if c.get("detail") else ""))
    if target == "solution":
        print("reference solution: %s" % ("verified" if p.returncode == 0 else "DOES NOT PASS (broken lab!)"))
        return p.returncode
    if p.returncode != 0:
        print("\nNot fixed yet. Read the README symptoms, observe, form a hypothesis, then fix app/ and re-run.")
        return 1
    levels = [int(x) for x in re.findall(r"[123]", a.hints)]
    hp = hint_cost(folder, levels)
    tp = min(20, max(0, math.ceil((a.minutes - 20) / 3.0))) if a.minutes else 0
    ok_rca, why_rca = rca_present(folder)
    ok_prev, why_prev = prevention(folder)
    score = max(0, 100 - hp - tp + (10 if ok_prev else 0))
    print("\nfault fixed and behaviour preserved")
    print("  root-cause note : %s (%s)" % ("yes" if ok_rca else "MISSING", why_rca))
    print("  prevention (+10): %s (%s)" % ("yes" if ok_prev else "no", why_prev))
    print("  score           : 100 - %d hints - %d time + %d prevention = %d" % (hp, tp, 10 if ok_prev else 0, score))
    if not ok_rca:
        print("\nINCOMPLETE: a fix without a written root cause is not a success. Fill in postmortem.md and re-run.")
        return 1
    print("\nSUCCESS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
