"""Shared helpers for the Broken-System Labs verifiers (stdlib only).

A scenario's verify.py builds a Verifier, adds checks, and calls finish().
Target selection (which code is verified):
    BROKEN_TARGET=app        (default) the learner's  <scenario>/app/
    BROKEN_TARGET=solution             the reference  <scenario>/solution/
    BROKEN_APP_DIR=/some/dir           explicit directory (used by the mutation checker)
Output: one JSON object on stdout {fixed, target, checks:[{name, ok, detail}], score}.
Exit code 0 only when every check passed.
"""
import json
import os
import subprocess
import sys

sys.dont_write_bytecode = True
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"


def target_dir(scenario_dir):
    explicit = os.environ.get("BROKEN_APP_DIR")
    if explicit:
        return os.path.abspath(explicit)
    which = os.environ.get("BROKEN_TARGET", "app")
    if which not in ("app", "solution"):
        raise SystemExit("BROKEN_TARGET must be 'app' or 'solution', got %r" % which)
    return os.path.join(scenario_dir, which)


class Verifier:
    def __init__(self, scenario_file):
        self.scenario_dir = os.path.dirname(os.path.abspath(scenario_file))
        self.target = target_dir(self.scenario_dir)
        self.checks = []

    def check(self, name, ok, detail=""):
        self.checks.append({"name": name, "ok": bool(ok), "detail": str(detail)[:400]})
        return bool(ok)

    def env(self, **extra):
        env = dict(os.environ)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env["PYTHONPATH"] = self.target
        env["BROKEN_TARGET_DIR"] = self.target
        env.update(extra)
        return env

    def pytest(self, name="existing behaviour tests stay green", subdir="tests", timeout=60):
        tests = os.path.join(self.target, subdir)
        if not os.path.isdir(tests):
            return self.check(name, False, "missing %s/ folder" % subdir)
        try:
            p = subprocess.run(
                [sys.executable, "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider", tests],
                cwd=self.target, env=self.env(), capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            return self.check(name, False, "tests timed out")
        tail = [l for l in p.stdout.strip().splitlines() if l.strip()][-1:] or [p.stderr.strip()[-200:]]
        return self.check(name, p.returncode == 0, tail[0])

    def probe(self, verify_file, mode, timeout=30):
        """Run `verify.py --probe <mode>` in a fresh interpreter against the target.
        The probe must print one JSON object on its last stdout line.
        Returns (data|None, error_text)."""
        try:
            p = subprocess.run(
                [sys.executable, os.path.abspath(verify_file), "--probe", mode],
                cwd=self.target, env=self.env(), capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            return None, "timed out after %ss (hang or runaway CPU)" % timeout
        lines = [l for l in p.stdout.strip().splitlines() if l.strip()]
        if p.returncode != 0 or not lines:
            err = (p.stderr.strip().splitlines() or ["no output"])[-1]
            return None, "probe crashed: " + err
        try:
            return json.loads(lines[-1]), ""
        except ValueError:
            return None, "probe printed invalid JSON"

    def finish(self):
        fixed = bool(self.checks) and all(c["ok"] for c in self.checks)
        result = {"fixed": fixed,
                  "target": os.path.relpath(self.target, self.scenario_dir) if not os.environ.get("BROKEN_APP_DIR") else self.target,
                  "checks": self.checks, "score": 100 if fixed else 0}
        print(json.dumps(result, indent=1))
        sys.exit(0 if fixed else 1)
