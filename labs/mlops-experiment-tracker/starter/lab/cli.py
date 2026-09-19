"""Command line interface (starter): ``python -m lab --db tracker.db <command> ...``."""

from __future__ import annotations

import sys
from collections.abc import Sequence
from typing import TextIO


def main(argv: Sequence[str] | None = None, *, stdout: TextIO | None = None, stderr: TextIO | None = None) -> int:
    """Run the CLI and return a process exit code: 0 ok, 1 domain error, 2 bad usage.

    Global option: ``--db PATH`` (required). Commands (build them with ``argparse`` sub-parsers):

    - ``start --experiment E [--name N] [--dataset-hash H] [--code-version V]``  prints the new run id
    - ``log-param RUN KEY VALUE``  |  ``log-metric RUN KEY VALUE(float) [--step N]``  |  ``end RUN [--status FINISHED|FAILED]``
    - ``best --experiment E --metric M [--mode max|min]``  prints the run id (error "no finished run ..." when none)
    - ``register --model M --run R``  prints the new version number
    - ``validate --model M --version N``
    - ``promote --model M --version N --stage Staging|Production|Archived [--metric M --threshold T
      --min-improvement X --lower-is-better]``  (Production needs --metric and --threshold; builds a PromotionPolicy)
    - ``rollback --model M [--reason TEXT]``  prints the restored version number
    - ``versions --model M``  prints one ``<version>\\t<stage>\\t<run_id>`` line per version

    TODO notes:
    - ``LabError`` (and ``FileNotFoundError``) -> print ``error: <message>`` to ``stderr`` and return 1.
    - argparse calls ``sys.exit(2)`` on bad usage; a function that is tested by calling it must RETURN 2 instead
      (catch ``SystemExit``). Use ``out = stdout or sys.stdout`` at call time so tests can capture output.
    """
    raise NotImplementedError("TODO: main")


if __name__ == "__main__":
    sys.exit(main())
