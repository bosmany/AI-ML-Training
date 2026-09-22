"""Command line: ``linkcheck URL [--depth N] [--concurrency N] ...``."""
from __future__ import annotations

import argparse
import asyncio  # noqa: F401
import json  # noqa: F401
import sys  # noqa: F401
from collections.abc import Callable, Coroutine, Sequence
from typing import Any

from .checker import crawl
from .models import CheckConfig, Report  # noqa: F401
from .parsing import normalize_url  # noqa: F401

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


def main(argv: Sequence[str] | None = None, *, crawler: Crawler = crawl) -> int:
    """Run the tool and RETURN the exit code (tests call ``main([...])``). The parser above is provided.

    TODO:
    - parse ``argv``; argparse raises ``SystemExit`` on usage errors: catch it and return its code (2)
    - build a ``CheckConfig`` and ``validate()`` it; also reject ``--depth < 0`` and a URL that does not start with
      http:// or https:// -> print ``linkcheck: error: ...`` to stderr and return ``EXIT_USAGE`` BEFORE any request
    - ``report = Report(start_url=normalize_url(args.url))`` then
      ``asyncio.run(crawler(args.url, config, depth=args.depth, report=report))`` (``crawler`` is injectable so tests
      can simulate Ctrl-C)
    - ``except KeyboardInterrupt``: ``report.interrupted = True`` and carry on to print the PARTIAL report
    - stdout: one line per broken result (sorted by URL)
      ``BROKEN <status value> <http status or -> <url> (linked from <sources>) <error>`` and finally
      ``checked N URLs, M broken`` (append `` (interrupted: partial report)`` when interrupted)
    - ``--report FILE``: write ``report.to_json_dict()`` as JSON (also for a partial report)
    - return ``EXIT_INTERRUPTED`` (130) if interrupted, else ``EXIT_BROKEN`` (1) if anything is broken, else 0
    """
    raise NotImplementedError
