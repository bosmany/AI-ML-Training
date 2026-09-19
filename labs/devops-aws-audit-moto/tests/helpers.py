"""Small helpers for injecting failures into REAL boto3 clients (still talking to moto)."""
from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from botocore.exceptions import ClientError

NOW = datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone.utc)


def client_error(code: str, operation: str = "Op") -> ClientError:
    return ClientError({"Error": {"Code": code, "Message": f"injected {code}"}}, operation)


def inject_error(client, event: str, code: str, times: int | None = None, status: int = 400) -> dict:
    """Make ``client`` fail on ``event`` (e.g. "ec2.DescribeInstances") with an AWS error code.

    ``times=None`` fails forever, ``times=N`` fails the first N calls and then lets calls through.
    Returns a dict whose ``calls`` counts every call seen.
    """
    state = {"calls": 0}

    def handler(**_kwargs):
        state["calls"] += 1
        if times is None or state["calls"] <= times:
            http = SimpleNamespace(status_code=status, headers={}, content=b"")
            return http, {"Error": {"Code": code, "Message": "injected"}, "ResponseMetadata": {"HTTPStatusCode": status}}
        return None  # let the real (moto) call happen

    client.meta.events.register(f"before-call.{event}", handler)
    return state


def count_calls(client, event: str) -> dict:
    state = {"calls": 0}

    def handler(**_kwargs):
        state["calls"] += 1

    client.meta.events.register(f"before-call.{event}", handler)
    return state


class Sleeper:
    """Injectable ``sleep`` that records instead of waiting."""

    def __init__(self) -> None:
        self.delays: list[float] = []

    def __call__(self, seconds: float) -> None:
        self.delays.append(seconds)
