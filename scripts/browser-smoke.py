#!/usr/bin/env python3
"""Browser smoke test for the course pages (Playwright + headless Chromium).

For every page that contains id="console-dock", plus index.html and (if present)
devops/interview-bank.html, this checks:

  * no uncaught JavaScript errors (`pageerror`) while loading / interacting;
    failed network requests (CDN, fonts, ...) are collected and reported separately
    as warnings and never fail the run;
  * the console minimize control (`.cd-min-btn`) toggles class `cd-min` on
    `#console-dock` and persists the choice in localStorage key `aimlZTH_console_min`
    across a reload (dock pages only);
  * no horizontal scroll (documentElement.scrollWidth <= clientWidth + 1) at 1280 px and
    1000 px viewport widths, with the dock expanded and minimized (pages without a dock:
    just the two widths);
  * on 3 sample pages, clicking a lesson "Run" button makes real output appear in
    `#cd-out` (this needs the real Pyodide, so those pages load it - every other page
    has the Pyodide CDN requests blocked to keep the run fast).

Usage:
    python scripts/browser-smoke.py                  # whole repo, serves it on port 8753
    python scripts/browser-smoke.py --only python/ch01-python-basics.html
    python scripts/browser-smoke.py --base-url http://localhost:8753   # use a running server
    python scripts/browser-smoke.py --pyodide-dir ~/.cache/pyodide-0.26.4   # serve Pyodide files locally
    python scripts/browser-smoke.py --json report.json
Exit code 0 = all good, 1 = at least one failure, 2 = setup problem.

Setup (CI does this): pip install playwright && python -m playwright install --with-deps chromium
(Locally the sandbox needs LD_LIBRARY_PATH pointing at the extracted chromium libs.)
"""
from __future__ import annotations

import argparse
import functools
import http.server
import json
import mimetypes
import os
import socket
import sys
import threading
import time
from pathlib import Path

try:
    from playwright.sync_api import Error as PWError
    from playwright.sync_api import TimeoutError as PWTimeout
    from playwright.sync_api import sync_playwright
except ImportError:  # pragma: no cover
    print("playwright is not installed: pip install playwright && python -m playwright install chromium", file=sys.stderr)
    sys.exit(2)

ROOT = Path(__file__).resolve().parent.parent
SKIP_DIRS = {".git", "node_modules", ".github", ".fastapi-venv", "scripts", "labs"}
STORAGE_KEY = "aimlZTH_console_min"
WIDTHS = (1280, 1000)
DEFAULT_SAMPLES = [
    "python/ch01-python-basics.html",
    "dsa/ds01-arrays-strings-hashing.html",
    "data/ch11-numpy-deep-dive.html",
]
PYODIDE_URL_PREFIX = "https://cdn.jsdelivr.net/pyodide/"


def discover_pages() -> list[str]:
    pages = []
    for p in sorted(ROOT.rglob("*.html")):
        rel = p.relative_to(ROOT)
        if any(part in SKIP_DIRS for part in rel.parts):
            continue
        rel_s = rel.as_posix()
        text = p.read_text(encoding="utf-8", errors="replace")
        if 'id="console-dock"' in text or rel_s in ("index.html", "devops/interview-bank.html"):
            pages.append(rel_s)
    return pages


def has_run_button(rel: str) -> bool:
    return 'class="cb-run"' in (ROOT / rel).read_text(encoding="utf-8", errors="replace")


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):  # noqa: D401
        pass


def start_server(port: int) -> tuple[http.server.ThreadingHTTPServer, int]:
    handler = functools.partial(QuietHandler, directory=str(ROOT))
    for p in (port, 0):
        try:
            srv = http.server.ThreadingHTTPServer(("127.0.0.1", p), handler)
            break
        except OSError:
            if p == 0:
                raise
            print(f"port {port} busy, falling back to a free port", file=sys.stderr)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, srv.server_address[1]


class Smoke:
    def __init__(self, browser, base: str, pyodide_dir: Path | None):
        self.browser = browser
        self.base = base
        self.pyodide_dir = pyodide_dir

    # -- context / page plumbing ------------------------------------------------------------
    def new_page(self, allow_pyodide: bool, width: int = 1280):
        ctx = self.browser.new_context(viewport={"width": width, "height": 800})
        page = ctx.new_page()
        state = {"errors": [], "net": [], "console": []}
        page.on("pageerror", lambda e: state["errors"].append(str(e).splitlines()[0][:300]))
        page.on("requestfailed", lambda r: state["net"].append(f"{r.url[:120]} ({(r.failure or '')})") if "blocked-by-smoke" not in (r.failure or "") and not r.url.startswith(self.base) else None)
        page.on("console", lambda m: state["console"].append(m.text[:200]) if m.type == "error" and "Failed to load resource" not in m.text else None)
        page.on("response", lambda r: state["net"].append(f"{r.url[:120]} (HTTP {r.status})") if r.status >= 400 else None)

        def handle(route):
            url = route.request.url
            if self.pyodide_dir is not None:
                name = url.split("/full/", 1)[-1].split("?", 1)[0]
                f = self.pyodide_dir / name
                if name and f.is_file():
                    ctype = "application/wasm" if name.endswith(".wasm") else (mimetypes.guess_type(name)[0] or "application/octet-stream")
                    route.fulfill(status=200, body=f.read_bytes(), headers={"content-type": ctype, "access-control-allow-origin": "*"})
                    return
            route.continue_()

        if allow_pyodide:
            if self.pyodide_dir is not None:
                page.route(PYODIDE_URL_PREFIX + "**", handle)
        else:
            # A loader that never finishes keeps the dock in its normal "Loading Python..." state
            # (aborting the script would put the page in its "Python offline" state instead) and
            # spares every page the ~10 MB Pyodide download.
            def stub(route):
                if route.request.url.endswith("/pyodide.js"):
                    route.fulfill(status=200, content_type="text/javascript", headers={"access-control-allow-origin": "*"},
                                  body="window.loadPyodide = function () { return new Promise(function () {}); };")
                else:
                    route.abort("blockedbyclient")

            page.route(PYODIDE_URL_PREFIX + "**", stub)
        return ctx, page, state

    @staticmethod
    def is_min(page) -> bool:
        return page.evaluate("document.getElementById('console-dock').classList.contains('cd-min')")

    @staticmethod
    def stored(page):
        return page.evaluate(f"localStorage.getItem('{STORAGE_KEY}')")

    def set_min(self, page, want: bool):
        if self.is_min(page) != want:
            page.click(".cd-min-btn", timeout=5000)
            page.wait_for_function(
                f"document.getElementById('console-dock').classList.contains('cd-min') === {str(want).lower()}", timeout=3000
            )

    @staticmethod
    def no_hscroll(page) -> tuple[bool, str]:
        sw, cw = page.evaluate("[document.documentElement.scrollWidth, document.documentElement.clientWidth]")
        return sw <= cw + 1, f"scrollWidth {sw} > clientWidth {cw}"

    # -- one page -----------------------------------------------------------------------------
    def check_page(self, rel: str) -> dict:
        res = {"page": rel, "failures": [], "warnings": [], "dock": False}
        url = f"{self.base}/{rel}"
        ctx, page, st = self.new_page(allow_pyodide=False)
        try:
            page.goto(url, wait_until="load", timeout=45000)
            page.wait_for_timeout(400)
            res["dock"] = page.locator("#console-dock").count() > 0
            has_btn = False
            if res["dock"]:
                self.check_minimize(page, url, res)
                has_btn = page.locator(".cd-min-btn").count() == 1
            for width in WIDTHS:
                page.set_viewport_size({"width": width, "height": 800})
                if res["dock"] and has_btn:
                    states = [("expanded", False), ("minimized", True)]
                elif res["dock"]:
                    states = [("page (no minimize button)", None)]
                else:
                    states = [("page", None)]
                for label, want in states:
                    if want is not None:
                        try:
                            self.set_min(page, want)
                        except PWError as e:
                            res["failures"].append(f"cannot put dock in {label} state at {width}px: {str(e)[:100]}")
                            continue
                    page.wait_for_timeout(150)
                    ok, why = self.no_hscroll(page)
                    if not ok:
                        res["failures"].append(f"horizontal scroll at {width}px ({label}): {why}")
        except (PWError, PWTimeout) as e:
            res["failures"].append(f"page could not be exercised: {str(e).splitlines()[0][:200]}")
        finally:
            for e in dict.fromkeys(st["errors"]):
                res["failures"].append(f"uncaught JS error: {e}")
            res["warnings"] += [f"network: {n}" for n in dict.fromkeys(st["net"])]
            res["warnings"] += [f"console.error: {c}" for c in dict.fromkeys(st["console"])]
            ctx.close()
        return res

    def check_minimize(self, page, url: str, res: dict):
        if page.locator(".cd-min-btn").count() != 1:
            res["failures"].append(f"expected exactly one .cd-min-btn, found {page.locator('.cd-min-btn').count()}")
            return
        page.set_viewport_size({"width": 1280, "height": 800})
        page.evaluate("localStorage.clear()")
        page.reload(wait_until="load")
        page.wait_for_selector(".cd-min-btn", timeout=10000)
        start = self.is_min(page)
        for step in range(2):  # toggle, reload -> persisted; toggle back, reload -> persisted
            page.click(".cd-min-btn")
            want = not start if step == 0 else start
            page.wait_for_timeout(150)
            if self.is_min(page) != want:
                res["failures"].append(f"clicking .cd-min-btn did not toggle #console-dock.cd-min (step {step + 1})")
                return
            expect_store = "1" if want else "0"
            if self.stored(page) != expect_store:
                res["failures"].append(f"localStorage[{STORAGE_KEY}] is {self.stored(page)!r} after toggle, expected {expect_store!r}")
                return
            page.reload(wait_until="load")
            page.wait_for_selector(".cd-min-btn", timeout=10000)
            if self.is_min(page) != want:
                res["failures"].append(f"minimized state ({want}) not restored after reload (step {step + 1})")
                return

    # -- real Run click ----------------------------------------------------------------------
    def check_run(self, rel: str, attempts: int = 2) -> dict:
        res = {"page": rel, "failures": [], "warnings": [], "output": ""}
        last = ""
        for attempt in range(attempts):
            ctx, page, st = self.new_page(allow_pyodide=True)
            try:
                page.goto(f"{self.base}/{rel}", wait_until="load", timeout=45000)
                page.wait_for_function(
                    "(() => { const s = document.getElementById('cd-status'); return s && /ready/i.test(s.textContent); })()", timeout=150000
                )
                self.set_min(page, False)
                idx = page.evaluate(
                    "[...document.querySelectorAll('.code-block')].findIndex(b => b.querySelector('.cb-run') && b.querySelector('.cb-code').textContent.includes('print('))"
                )
                if idx < 0:
                    res["failures"].append("no lesson block with a Run button that prints")
                    return res
                page.evaluate("document.getElementById('cd-out').innerHTML = ''")
                page.locator(".code-block").nth(idx).locator(".cb-run").click()
                page.wait_for_function(
                    "[...document.querySelectorAll('#cd-out .cl')].some(e => e.classList.contains('out') || e.classList.contains('err'))", timeout=120000
                )
                page.wait_for_timeout(300)
                lines = page.evaluate(
                    "[...document.querySelectorAll('#cd-out .cl')].map(e => [e.className, e.textContent])"
                )
                outs = [t for c, t in lines if "out" in c.split() and t.strip()]
                errs = [t for c, t in lines if "err" in c.split()]
                res["output"] = " | ".join(outs)[:160]
                if errs:
                    res["failures"].append(f"Run produced an error in the console: {errs[0][:160]}")
                elif not outs:
                    res["failures"].append("Run click produced no output lines in #cd-out")
                for e in dict.fromkeys(st["errors"]):
                    res["failures"].append(f"uncaught JS error: {e}")
                res["warnings"] += [f"network: {n}" for n in dict.fromkeys(st["net"])]
                return res
            except (PWError, PWTimeout) as e:
                last = str(e).splitlines()[0][:200]
                if attempt + 1 < attempts:
                    time.sleep(2)
            finally:
                ctx.close()
        res["failures"].append(f"Pyodide did not load / Run did not produce output after {attempts} attempts: {last}")
        return res


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", type=int, default=8753)
    ap.add_argument("--base-url", help="use an already running server instead of starting one")
    ap.add_argument("--only", action="append", help="restrict to these pages (repo-relative), repeatable")
    ap.add_argument("--sample", action="append", help="pages for the Run-click check (default: 3 built-in)")
    ap.add_argument("--skip-run", action="store_true", help="skip the Pyodide Run-click check")
    ap.add_argument("--pyodide-dir", help="serve the Pyodide CDN requests of the Run check from this local dir")
    ap.add_argument("--json", help="write a JSON report here")
    args = ap.parse_args()

    pages = discover_pages()
    if args.only:
        pages = [p for p in pages if p in set(args.only)]
    if not pages:
        print("no pages selected", file=sys.stderr)
        return 2
    samples = args.sample or [s for s in DEFAULT_SAMPLES if (ROOT / s).exists() and has_run_button(s)]
    if len(samples) < 3 and not args.sample:
        extra = [p for p in pages if p not in samples and has_run_button(p)]
        samples += extra[: 3 - len(samples)]
    if args.only and not args.sample:
        samples = [s for s in samples if s in set(args.only)]

    srv = None
    base = args.base_url.rstrip("/") if args.base_url else None
    if base is None:
        srv, port = start_server(args.port)
        base = f"http://127.0.0.1:{port}"
    print(f"serving {ROOT} at {base}; {len(pages)} page(s), {0 if args.skip_run else len(samples)} Run-click sample(s)")

    pyodide_dir = Path(args.pyodide_dir).expanduser() if args.pyodide_dir else None
    report = {"pages": [], "runs": []}
    failed = 0
    try:
        with sync_playwright() as pw:
            try:
                browser = pw.chromium.launch(headless=True)
            except PWError as e:
                print(f"cannot launch Chromium: {str(e).splitlines()[0]}", file=sys.stderr)
                return 2
            smoke = Smoke(browser, base, pyodide_dir)
            for rel in pages:
                r = smoke.check_page(rel)
                report["pages"].append(r)
                status = "FAIL" if r["failures"] else "ok  "
                failed += bool(r["failures"])
                print(f"{status} {rel}{'' if r['dock'] else '  (no console dock)'}")
                for f in r["failures"]:
                    print(f"       - {f}")
            if not args.skip_run:
                print("\nRun-click checks (real Pyodide):")
                for rel in samples:
                    r = smoke.check_run(rel)
                    report["runs"].append(r)
                    failed += bool(r["failures"])
                    print(f"{'FAIL' if r['failures'] else 'ok  '} run {rel}  -> {r['output']!r}")
                    for f in r["failures"]:
                        print(f"       - {f}")
            browser.close()
    finally:
        if srv:
            srv.shutdown()

    warns = [(r["page"], w) for r in report["pages"] + report["runs"] for w in r["warnings"]]
    print(f"\nNetwork/console warnings (do not fail the run): {len(warns)}")
    for page, w in warns[:40]:
        print(f"  {page}: {w}")
    if len(warns) > 40:
        print(f"  ... {len(warns) - 40} more")
    total = len(report["pages"]) + len(report["runs"])
    print(f"\n{total - failed}/{total} checks passed" + ("" if not failed else f"  ({failed} FAILED)"))
    if args.json:
        Path(args.json).write_text(json.dumps(report, indent=2))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
