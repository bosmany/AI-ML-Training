"""boto3 client factory, retry-with-backoff and a pagination helper that survives throttling."""
from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any, TypeVar

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

T = TypeVar("T")

RETRYABLE_CODES = frozenset({
    "Throttling", "ThrottlingException", "ThrottledException", "RequestLimitExceeded",
    "TooManyRequestsException", "ProvisionedThroughputExceededException", "SlowDown",
    "RequestThrottled", "ServiceUnavailable", "InternalError", "InternalFailure", "RequestTimeout",
})


def make_client(service: str, region: str = "us-east-1"):
    """Return a boto3 client for ``service``.

    TODO: pass a botocore ``Config`` with region_name, connect_timeout, read_timeout and
    ``retries={"total_max_attempts": 1, "mode": "standard"}`` - botocore's own retries would sleep for
    real and hide the throttling from our (injectable-sleep) retry logic.
    Credentials are NOT set here: they come from the environment (fake ones in the tests).
    """
    raise NotImplementedError


def error_code(exc: ClientError) -> str:
    return exc.response.get("Error", {}).get("Code", "Unknown")


def is_retryable(exc: BaseException) -> bool:
    """True only for ClientErrors whose code is in RETRYABLE_CODES."""
    raise NotImplementedError


def retry_call(
    fn: Callable[[], T],
    *,
    max_attempts: int = 5,
    base_delay: float = 0.5,
    max_delay: float = 8.0,
    sleep: Callable[[float], None] = time.sleep,
) -> T:
    """Call ``fn`` until it succeeds.

    TODO:
    - retry only retryable ClientErrors; anything else propagates immediately (no sleep).
    - between attempts call ``sleep(min(base_delay * 2**n, max_delay))`` (n = 0 for the first retry).
    - after ``max_attempts`` attempts re-raise the LAST error (no sleep after the final attempt).
    """
    raise NotImplementedError


def list_all(
    client: Any,
    operation: str,
    result_key: str,
    *,
    page_size: int | None = None,
    max_attempts: int = 5,
    sleep: Callable[[float], None] = time.sleep,
    params: dict[str, Any] | None = None,
) -> list[Any]:
    """Collect every item of ``result_key`` across all pages of ``operation`` (e.g. "describe_instances").

    TODO: use ``client.get_paginator(operation).paginate(PaginationConfig={"PageSize": page_size}, **params)``
    (omit PageSize when None). Wrap the WHOLE collection in ``retry_call`` so that a throttle on page 3
    restarts the listing from scratch instead of producing duplicates.
    """
    raise NotImplementedError
