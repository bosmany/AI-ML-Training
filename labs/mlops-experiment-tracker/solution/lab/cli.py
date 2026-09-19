"""Command line interface (reference solution): ``python -m lab --db tracker.db <command> ...``."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from typing import TextIO

from lab.errors import LabError
from lab.models import PromotionPolicy, Stage
from lab.registry import Registry
from lab.tracker import Tracker


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="tracker", description="Mini experiment tracker + model registry")
    parser.add_argument("--db", required=True, help="path of the SQLite database file")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("start", help="start a run and print its id")
    p.add_argument("--experiment", required=True)
    p.add_argument("--name")
    p.add_argument("--dataset-hash")
    p.add_argument("--code-version")

    p = sub.add_parser("log-param")
    p.add_argument("run_id"), p.add_argument("key"), p.add_argument("value")

    p = sub.add_parser("log-metric")
    p.add_argument("run_id"), p.add_argument("key"), p.add_argument("value", type=float)
    p.add_argument("--step", type=int, default=0)

    p = sub.add_parser("end")
    p.add_argument("run_id")
    p.add_argument("--status", choices=["FINISHED", "FAILED"], default="FINISHED")

    p = sub.add_parser("best", help="print the id of the best finished run")
    p.add_argument("--experiment", required=True)
    p.add_argument("--metric", required=True)
    p.add_argument("--mode", choices=["max", "min"], default="max")

    p = sub.add_parser("register", help="register a finished run as a new model version; prints the version")
    p.add_argument("--model", required=True)
    p.add_argument("--run", required=True)

    p = sub.add_parser("validate", help="mark a model version as validated")
    p.add_argument("--model", required=True)
    p.add_argument("--version", type=int, required=True)

    p = sub.add_parser("promote", help="move a version to another stage (Production is gated)")
    p.add_argument("--model", required=True)
    p.add_argument("--version", type=int, required=True)
    p.add_argument("--stage", required=True, choices=[s.value for s in Stage if s is not Stage.NONE])
    p.add_argument("--metric")
    p.add_argument("--threshold", type=float)
    p.add_argument("--min-improvement", type=float, default=0.0)
    p.add_argument("--lower-is-better", action="store_true")

    p = sub.add_parser("rollback")
    p.add_argument("--model", required=True)
    p.add_argument("--reason", default="")

    p = sub.add_parser("versions", help="list versions: <version> <stage> <run_id>")
    p.add_argument("--model", required=True)
    return parser


def _dispatch(args: argparse.Namespace, out: TextIO) -> int:
    if args.command in {"start", "log-param", "log-metric", "end", "best"}:
        with Tracker(args.db) as tracker:
            if args.command == "start":
                print(tracker.start_run(args.experiment, name=args.name, dataset_hash=args.dataset_hash, code_version=args.code_version), file=out)
            elif args.command == "log-param":
                tracker.log_param(args.run_id, args.key, args.value)
            elif args.command == "log-metric":
                tracker.log_metric(args.run_id, args.key, args.value, step=args.step)
            elif args.command == "end":
                tracker.end_run(args.run_id, args.status)
            else:
                best = tracker.best_run(args.experiment, args.metric, mode=args.mode)
                if best is None:
                    raise LabError(f"no finished run in {args.experiment!r} has metric {args.metric!r}")
                print(best, file=out)
        return 0
    with Registry(args.db) as registry:
        if args.command == "register":
            print(registry.register_version(args.model, args.run), file=out)
        elif args.command == "validate":
            registry.mark_validated(args.model, args.version)
        elif args.command == "promote":
            stage = Stage(args.stage)
            policy = None
            if stage is Stage.PRODUCTION:
                if args.metric is None or args.threshold is None:
                    raise LabError("promoting to Production needs --metric and --threshold")
                policy = PromotionPolicy(args.metric, args.threshold, args.min_improvement, not args.lower_is_better)
            registry.transition(args.model, args.version, stage, policy=policy)
        elif args.command == "rollback":
            print(registry.rollback(args.model, reason=args.reason), file=out)
        else:
            for v in registry.list_versions(args.model):
                print(f"{v.version}\t{v.stage.value}\t{v.run_id}", file=out)
    return 0


def main(argv: Sequence[str] | None = None, *, stdout: TextIO | None = None, stderr: TextIO | None = None) -> int:
    """Run the CLI. Returns 0 on success, 1 on a domain error (message on stderr), 2 on bad usage."""
    out, err = stdout or sys.stdout, stderr or sys.stderr
    try:
        args = build_parser().parse_args(argv)
    except SystemExit as exc:  # argparse exits on bad usage; a library-style main() must return instead
        return int(exc.code or 0)
    try:
        return _dispatch(args, out)
    except LabError as exc:
        print(f"error: {exc}", file=err)
        return 1
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=err)
        return 1


if __name__ == "__main__":
    sys.exit(main())
