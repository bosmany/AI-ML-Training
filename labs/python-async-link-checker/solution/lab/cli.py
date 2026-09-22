"""Command line: ``linkcheck URL [--depth N] [--concurrency N] ...``."""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections.abc import Callable, Coroutine, Sequence
from typing import Any

from .checker import crawl
from .models import CheckConfig, Report
from .parsing import normalize_url

EXIT_OK = 0
EXIT_BROKEN = 1
EXIT_USAGE = 2
EXIT_INTERRUPTED = 130

Crawler = Callable[..., Coroutine[Any, Any, Report]]


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="linkcheck", description="Check every link reachable from a page.")
    p.add_argument("url", help="start page, e.g. https://example.com/")
    p.add_argument("--depth", type=int, default=1, help="how many same-host page hops to follow (default 1)")
    p.add_argument("--concurrency", type=int, default=10, help="max requests in flight (default 10)")
    p.add_argument("--timeout", type=float, default=10.0, help="total seconds per request (default 10)")
    p.add_argument("--connect-timeout", type=float, default=5.0, help="connect seconds (default 5)")
    p.add_argument("--retries", type=int, default=0, help="extra attempts for transient errors (default 0)")
    p.add_argument("--report", metavar="FILE", help="write the JSON report to FILE")
    return p


def _print_summary(report: Report) -> None:
    for result in report.broken:
        sources = ", ".join(s for s, t in report.edges if t == result.url and s) or "-"
        detail = result.error or ""
        print(f"BROKEN {result.status.value} {result.http_status or '-'} {result.url} (linked from {sources}) {detail}".rstrip())
    suffix = " (interrupted: partial report)" if report.interrupted else ""
    print(f"checked {len(report.results)} URLs, {len(report.broken)} broken{suffix}")


def main(argv: Sequence[str] | None = None, *, crawler: Crawler = crawl) -> int:
    """Return 0 (all links fine), 1 (broken links), 2 (usage error) or 130 (interrupted; partial report printed)."""
    try:
        args = build_parser().parse_args(argv)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else EXIT_USAGE
    config = CheckConfig(concurrency=args.concurrency, timeout=args.timeout, connect_timeout=args.connect_timeout,
                         retries=args.retries)
    try:
        config.validate()
        if args.depth < 0:
            raise ValueError("depth must be >= 0")
        if not args.url.lower().startswith(("http://", "https://")):
            raise ValueError("url must start with http:// or https://")
    except ValueError as exc:
        print(f"linkcheck: error: {exc}", file=sys.stderr)
        return EXIT_USAGE

    report = Report(start_url=normalize_url(args.url))
    try:
        asyncio.run(crawler(args.url, config, depth=args.depth, report=report))
    except KeyboardInterrupt:
        report.interrupted = True
    _print_summary(report)
    if args.report:
        with open(args.report, "w", encoding="utf-8") as fh:
            json.dump(report.to_json_dict(), fh, indent=2)
    if report.interrupted:
        return EXIT_INTERRUPTED
    return EXIT_BROKEN if report.broken else EXIT_OK
