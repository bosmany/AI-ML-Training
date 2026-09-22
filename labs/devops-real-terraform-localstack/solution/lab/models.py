"""Dataclasses shared by every module. Provided complete - you do not need to change this file."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class StackConfig:
    """Everything needed to create (or re-create) one instance of the demo stack.

    Mirrors the Terraform variables in ``terraform/variables.tf`` one-to-one: whatever you can
    set with ``-var`` there, you can set here.
    """

    endpoint_url: str
    handler_path: Path
    region: str = "us-east-1"
    bucket_name: str = "tf-localstack-demo-bucket"
    role_name: str = "tf-localstack-demo-role"
    policy_name: str = "tf-localstack-demo-role-policy"
    function_name: str = "tf-localstack-demo-fn"


@dataclass(frozen=True)
class StackOutputs:
    """Mirrors ``terraform/outputs.tf``."""

    bucket_arn: str
    role_arn: str
    function_arn: str


@dataclass(frozen=True)
class Finding:
    """One problem ``audit_stack`` found with an already-applied stack."""

    check: str
    resource: str
    severity: str
    message: str
    details: dict[str, Any]
