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
    """boto3 client with timeouts and botocore's OWN retries disabled (we retry, with an injectable sleep)."""
    cfg = Config(
        region_name=region,
        connect_timeout=5,
        read_timeout=30,
        retries={"total_max_attempts": 1, "mode": "standard"},
    )
    return boto3.client(service, config=cfg)


def error_code(exc: ClientError) -> str:
    return exc.response.get("Error", {}).get("Code", "Unknown")


def is_retryable(exc: BaseException) -> bool:
    return isinstance(exc, ClientError) and error_code(exc) in RETRYABLE_CODES


def retry_call(
    fn: Callable[[], T],
    *,
    max_attempts: int = 5,
    base_delay: float = 0.5,
    max_delay: float = 8.0,
    sleep: Callable[[float], None] = time.sleep,
) -> T:
    """Call ``fn`` until it succeeds. Retry only retryable ClientErrors, sleeping base*2**n (capped).

    The last error is re-raised after ``max_attempts`` attempts. Everything else propagates at once.
    """
    for attempt in range(1, max_attempts + 1):
        try:
            return fn()
        except ClientError as exc:
            if not is_retryable(exc) or attempt == max_attempts:
                raise
            sleep(min(base_delay * 2 ** (attempt - 1), max_delay))
    raise AssertionError("unreachable")  # pragma: no cover


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
    """Collect every item of ``result_key`` across all pages of ``operation``.

    If a page is throttled part-way through, the whole listing is restarted (inside ``retry_call``)
    so a retry can never produce duplicates.
    """
    paginator = client.get_paginator(operation)
    config = {"PageSize": page_size} if page_size else {}

    def collect() -> list[Any]:
        items: list[Any] = []
        for page in paginator.paginate(PaginationConfig=config, **(params or {})):
            items.extend(page.get(result_key, []))
        return items

    return retry_call(collect, max_attempts=max_attempts, sleep=sleep)
