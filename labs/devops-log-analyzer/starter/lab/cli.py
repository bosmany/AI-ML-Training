"""Command line interface. ``main(argv) -> int`` so tests can call it without subprocess."""
from __future__ import annotations

import argparse

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
    """Run the tool and RETURN an exit code (never call sys.exit here).

    TODO:
    1. parse args; argparse raises SystemExit on bad input/--help: catch it and return its code (2 for errors).
    2. reject --top < 1, --bf-threshold < 1, --bf-window <= 0 (exit 2, message on stderr).
    3. open the file (utf-8, errors="replace") or read sys.stdin when logfile == "-"; STREAM it into
       ``analyze`` (never .read()/.readlines()). Unreadable file -> message on stderr, exit 2.
    4. a file with lines but ZERO valid ones is the wrong input -> stderr message, exit 2.
       (An EMPTY file is fine: zero report, exit 0.)
    5. print render_json / render_text to STDOUT (diagnostics only to stderr).
    6. if --fail-on-error-rate was given and error_rate is STRICTLY greater -> message on stderr, exit 1.
    """
    raise NotImplementedError
