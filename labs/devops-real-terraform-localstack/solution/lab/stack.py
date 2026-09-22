"""``apply_stack`` is the Python equivalent of ``terraform apply``: converge the bucket, the
role+policy and the function to the state ``cfg`` describes, in the only order that can work
(the function's role must exist before the function can reference it)."""
from __future__ import annotations

from typing import Any

from .iam import ensure_lambda_role
from .lambda_ import build_deployment_package, ensure_function
from .models import StackConfig, StackOutputs
from .s3 import ensure_bucket


def apply_stack(cfg: StackConfig, clients: dict[str, Any]) -> StackOutputs:
    """Create or converge the whole demo stack and return its outputs.

    Safe to call more than once with the same ``cfg`` (each step it calls is itself idempotent),
    exactly like running ``terraform apply`` twice in a row with no changes made in between.
    """
    bucket_arn = ensure_bucket(clients["s3"], cfg)
    role_arn = ensure_lambda_role(clients["iam"], cfg)
    zip_bytes = build_deployment_package(cfg.handler_path)
    function_arn = ensure_function(clients["lambda"], cfg, role_arn, zip_bytes)
    return StackOutputs(bucket_arn=bucket_arn, role_arn=role_arn, function_arn=function_arn)
