#!/usr/bin/env python3
"""Execute the course notebooks and check the committed copies stay clean.

For every fastapi/*.ipynb (override with --glob) this

  1. copies the notebook into a fresh temp directory and executes it there with nbclient
     (never inside the repo, so notebooks that write files / sqlite databases cannot dirty it);
  2. asserts the executed copy has no error outputs (`output_type == "error"`, or a stream on
     stderr containing a Traceback) and that code cells have sequential execution counts 1..N;
  3. asserts the COMMITTED notebook (the file in the repo, untouched) has no error outputs,
     sequential execution counts, and no absolute local paths in its outputs
     (`/home/`, `/tmp/`, `/Users/`, `/private/var/`, `C:\\Users`).

The first code cell of each notebook is normally `!pip install ...`; it runs as-is (fast when the
packages are present). `--skip-pip` blanks such lines for offline runs.

Usage:
    python scripts/check-notebooks.py
    python scripts/check-notebooks.py --glob 'fastapi/ch36*.ipynb' --timeout 300
    python scripts/check-notebooks.py --json report.json
Requires: pip install nbclient nbformat ipykernel (+ whatever the notebooks install themselves).
Exit code 0 = all good, 1 = a check failed, 2 = setup problem.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import tempfile
import time
from pathlib import Path

try:
    import nbformat
    from nbclient import NotebookClient
    from nbclient.exceptions import CellExecutionError, CellTimeoutError
except ImportError:  # pragma: no cover
    print("nbclient/nbformat are not installed: pip install nbclient nbformat ipykernel", file=sys.stderr)
    sys.exit(2)

ROOT = Path(__file__).resolve().parent.parent
PATH_PATTERNS = [r"/home/", r"/tmp/", r"/Users/", r"/private/var/", r"[A-Za-z]:\\Users\\"]
PATH_RE = re.compile("|".join(PATH_PATTERNS))


def output_texts(cell) -> list[str]:
    """Every piece of text a cell's outputs carry (streams, results, errors incl. tracebacks)."""
    texts: list[str] = []
    for out in cell.get("outputs", []):
        t = out.get("output_type")
        if t == "stream":
            texts.append("".join(out.get("text", "")))
        elif t in ("execute_result", "display_data"):
            for v in out.get("data", {}).values():
                texts.append("".join(v) if isinstance(v, list) else json.dumps(v) if not isinstance(v, str) else v)
        elif t == "error":
            texts.append(out.get("ename", "") + ": " + out.get("evalue", ""))
            texts.extend(out.get("traceback", []))
    return texts


def error_outputs(nb) -> list[str]:
    problems = []
    for i, c in enumerate(nb.cells):
        if c.cell_type != "code":
            continue
        for out in c.get("outputs", []):
            if out.get("output_type") == "error":
                problems.append(f"cell {i}: {out.get('ename')}: {str(out.get('evalue'))[:120]}")
            elif out.get("output_type") == "stream" and out.get("name") == "stderr" and "Traceback (most recent call last)" in "".join(out.get("text", "")):
                problems.append(f"cell {i}: Traceback printed on stderr")
    return problems


def sequential(nb) -> str:
    counts = [c.get("execution_count") for c in nb.cells if c.cell_type == "code"]
    if all(c is None for c in counts):
        return "no execution counts recorded"
    expected = list(range(1, len(counts) + 1))
    if counts != expected:
        return f"execution counts {counts} are not sequential 1..{len(counts)}"
    return ""


def local_paths(nb) -> list[str]:
    hits = []
    for i, c in enumerate(nb.cells):
        if c.cell_type != "code":
            continue
        for t in output_texts(c):
            m = PATH_RE.search(t)
            if m:
                start = max(0, m.start() - 30)
                hits.append(f"cell {i}: ...{t[start:m.end() + 40]!r}")
                break
    return hits


def check_notebook(path: Path, timeout: int, skip_pip: bool) -> dict:
    rel = path.relative_to(ROOT).as_posix()
    res = {"notebook": rel, "failures": [], "seconds": 0.0}
    t0 = time.time()
    committed = nbformat.read(path, as_version=4)

    # --- committed copy hygiene ---
    for p in error_outputs(committed):
        res["failures"].append(f"committed notebook has an error output: {p}")
    seq = sequential(committed)
    if seq:
        res["failures"].append(f"committed notebook: {seq}")
    for h in local_paths(committed):
        res["failures"].append(f"committed notebook leaks an absolute local path in outputs: {h}")

    # --- execute a copy in a temp dir ---
    tmp = Path(tempfile.mkdtemp(prefix="nbcheck-"))
    try:
        work = tmp / path.name
        shutil.copy2(path, work)
        nb = nbformat.read(work, as_version=4)
        if skip_pip:
            for c in nb.cells:
                if c.cell_type == "code":
                    c.source = "\n".join(l for l in c.source.split("\n") if not l.lstrip().startswith(("!pip", "%pip")))
        client = NotebookClient(nb, timeout=timeout, kernel_name="python3", resources={"metadata": {"path": str(tmp)}}, allow_errors=True)
        try:
            client.execute()
        except CellTimeoutError as e:
            res["failures"].append(f"execution timed out after {timeout}s per cell: {str(e).splitlines()[0][:150]}")
        except CellExecutionError as e:  # pragma: no cover (allow_errors=True)
            res["failures"].append(f"execution error: {str(e).splitlines()[0][:150]}")
        except Exception as e:  # kernel died, missing kernel, ...
            res["failures"].append(f"could not execute: {type(e).__name__}: {str(e).splitlines()[0][:150] if str(e) else ''}")
        else:
            for p in error_outputs(nb):
                res["failures"].append(f"execution produced an error: {p}")
            seq = sequential(nb)
            if seq:
                res["failures"].append(f"executed copy: {seq}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    res["seconds"] = round(time.time() - t0, 1)
    return res


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--glob", default="fastapi/*.ipynb", help="notebooks to check, relative to the repo root")
    ap.add_argument("--timeout", type=int, default=300, help="per-cell timeout in seconds")
    ap.add_argument("--skip-pip", action="store_true", help="blank out !pip/%%pip lines (offline runs)")
    ap.add_argument("--json", help="write a JSON report here")
    args = ap.parse_args()

    # `!pip` inside the kernel must hit the same interpreter that runs this script
    bindir = str(Path(sys.executable).parent)
    os.environ["PATH"] = bindir + os.pathsep + os.environ.get("PATH", "")
    os.environ.setdefault("PYTHONWARNINGS", "ignore")

    nbs = sorted(ROOT.glob(args.glob))
    if not nbs:
        print(f"no notebooks match {args.glob}", file=sys.stderr)
        return 2
    results = []
    for nb in nbs:
        r = check_notebook(nb, args.timeout, args.skip_pip)
        results.append(r)
        print(f"{'FAIL' if r['failures'] else 'ok  '} {r['notebook']}  ({r['seconds']}s)")
        for f in r["failures"]:
            print(f"       - {f}")
    bad = sum(bool(r["failures"]) for r in results)
    print(f"\n{len(results) - bad}/{len(results)} notebooks passed")
    if args.json:
        Path(args.json).write_text(json.dumps(results, indent=2))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
