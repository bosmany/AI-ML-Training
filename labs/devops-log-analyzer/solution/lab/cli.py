"""Command line interface. ``main(argv) -> int`` so tests can call it without subprocess."""
from __future__ import annotations

import argparse
import sys
from datetime import timedelta

from .analyzer import analyze
from .render import render_json, render_text

EXIT_OK = 0
EXIT_THRESHOLD = 1  # --fail-on-error-rate exceeded
EXIT_USAGE = 2  # bad arguments, unreadable file, or input that is not an access log at all


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="log-analyzer", description="Stream an nginx combined log and report.")
    p.add_argument("logfile", help="path to the log file, or '-' for stdin")
    p.add_argument("--format", choices=["text", "json"], default="text")
    p.add_argument("--top", type=int, default=5, help="how many top IPs/paths to show")
    p.add_argument("--fail-on-error-rate", type=float, default=None, metavar="X",
                   help="exit 1 if the overall 5xx rate is STRICTLY greater than X (a fraction, 0.05 = 5%%)")
    p.add_argument("--bf-threshold", type=int, default=5, help="401/403 count that makes an IP suspicious")
    p.add_argument("--bf-window", type=float, default=60.0, help="sliding window in seconds")
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:  # argparse exits; convert to a return code
        return exc.code if isinstance(exc.code, int) else EXIT_USAGE
    if args.top < 1 or args.bf_threshold < 1 or args.bf_window <= 0:
        print("error: --top, --bf-threshold and --bf-window must be positive", file=sys.stderr)
        return EXIT_USAGE

    try:
        if args.logfile == "-":
            report = analyze(sys.stdin, args.top, args.bf_threshold, timedelta(seconds=args.bf_window))
        else:
            # errors="replace": binary junk becomes a malformed line instead of a crash.
            with open(args.logfile, encoding="utf-8", errors="replace") as fh:
                report = analyze(fh, args.top, args.bf_threshold, timedelta(seconds=args.bf_window))
    except OSError as exc:
        print(f"error: cannot read {args.logfile}: {exc.strerror or exc}", file=sys.stderr)
        return EXIT_USAGE

    if report.parsed == 0 and report.skipped > 0:
        # Every line was garbage: probably the wrong file/format. Do not let a CI gate pass silently.
        print(f"error: none of the {report.skipped} lines are valid combined-format log lines", file=sys.stderr)
        return EXIT_USAGE

    print(render_json(report) if args.format == "json" else render_text(report))

    if args.fail_on_error_rate is not None and report.error_rate > args.fail_on_error_rate:
        print(
            f"FAIL: 5xx rate {report.error_rate:.2%} exceeds limit {args.fail_on_error_rate:.2%}",
            file=sys.stderr,
        )
        return EXIT_THRESHOLD
    return EXIT_OK
