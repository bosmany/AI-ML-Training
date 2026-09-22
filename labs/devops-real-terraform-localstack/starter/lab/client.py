"""boto3 clients configured to talk to a real LocalStack endpoint instead of real AWS."""
from __future__ import annotations

from typing import Any

import boto3
from botocore.config import Config

from .models import StackConfig

# LocalStack has no real credentials to check; any non-empty string works, and using an
# obviously-fake pair (matching the moto lab's convention) makes it impossible to ever hit a
# real AWS account by accident, even if endpoint_url were left unset.
_FAKE_ACCESS_KEY = "test"
_FAKE_SECRET_KEY = "test"


def make_clients(cfg: StackConfig) -> dict[str, Any]:
    """Return ``{"s3": ..., "iam": ..., "lambda": ...}``, real boto3 clients pointed at
    ``cfg.endpoint_url`` (LocalStack's single edge port, e.g. ``http://127.0.0.1:4566``).

    - S3 needs ``s3={"addressing_style": "path"}``: LocalStack does not do virtual-hosted-style
      bucket DNS (``bucket.s3.amazonaws.com``), so path-style (``s3.amazonaws.com/bucket``) is
      required or every S3 call fails to resolve.
    - IAM is a global service on real AWS (no region in its endpoint) but boto3 still requires
      *a* region to construct the client; ``cfg.region`` is fine for both.
    - Lambda function creation and cold starts can take longer than boto3's 60s default read
      timeout under load; give it more room (``connect_timeout=10, read_timeout=90``).

    Use ``aws_access_key_id=_FAKE_ACCESS_KEY, aws_secret_access_key=_FAKE_SECRET_KEY,
    endpoint_url=cfg.endpoint_url, region_name=cfg.region`` for all three clients.
    """
    raise NotImplementedError
