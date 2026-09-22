#!/usr/bin/env python3
"""Contract check for every runnable lab under broken/:
verify.py must FAIL on the untouched broken app/ and PASS on solution/ (and stay under 60 s).

    python broken/check_contract.py            # all labs
    python broken/check_contract.py 01 04
"""
import glob
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REQUIRED = ["README.md", "verify.py", "hints.json", "postmortem_template.md", "solution/ROOT_CAUSE.md"]


def run(folder, target):
    env = dict(os.environ, BROKEN_TARGET=target, PYTHONDONTWRITEBYTECODE="1")
    t = time.time()
    p = subprocess.run([sys.executable, os.path.join(folder, "verify.py")], cwd=folder, env=env,
                       capture_output=True, text=True, timeout=120)
    return p.returncode, time.time() - t, p.stdout


def main():
    wanted = {a.zfill(2) for a in sys.argv[1:]}
    folders = [os.path.dirname(v) for v in sorted(glob.glob(os.path.join(HERE, "[0-9][0-9]-*", "verify.py")))]
    bad = 0
    print("%-32s %-14s %-14s %s" % ("LAB", "BROKEN app/", "SOLUTION", "FILES"))
    for f in folders:
        name = os.path.basename(f)
        if wanted and name[:2] not in wanted:
            continue
        rc_b, t_b, _ = run(f, "app")
        rc_s, t_s, out_s = run(f, "solution")
        missing = [r for r in REQUIRED if not os.path.exists(os.path.join(f, r))]
        try:
            hints = json.load(open(os.path.join(f, "hints.json")))["hints"]
            if [h["level"] for h in hints] != [1, 2, 3]:
                missing.append("hints.json levels")
        except Exception:
            missing.append("hints.json unreadable")
        ok = rc_b != 0 and rc_s == 0 and not missing and max(t_b, t_s) < 60
        bad += not ok
        print("%-32s %-14s %-14s %s%s" % (name, ("fails (ok)" if rc_b else "PASSES (bad)") + " %.1fs" % t_b,
                                        ("passes (ok)" if rc_s == 0 else "FAILS (bad)") + " %.1fs" % t_s,
                                        "ok" if not missing else "missing: " + ", ".join(missing), "" if ok else "   <-- FIX"))
    print("\n%s" % ("all labs satisfy the contract" if not bad else "%d lab(s) violate the contract" % bad))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
