"""Real S3 + IAM + Lambda stack, provisioned and verified with real boto3 against real LocalStack.

This is the Python-only path through the same three resources ``terraform/main.tf`` describes
(see the lab README): useful on its own as "how would I create this with boto3 directly", and
here it stands in for `terraform apply` / `terraform show` inside the automated test suite,
since the terraform binary is not assumed to be installed.
"""
from .models import Finding, StackConfig, StackOutputs
from .client import make_clients
from .s3 import ensure_bucket
from .iam import ensure_lambda_role
from .lambda_ import build_deployment_package, ensure_function, invoke
from .stack import apply_stack
from .audit import audit_stack

__all__ = [
    "Finding",
    "StackConfig",
    "StackOutputs",
    "make_clients",
    "ensure_bucket",
    "ensure_lambda_role",
    "build_deployment_package",
    "ensure_function",
    "invoke",
    "apply_stack",
    "audit_stack",
]
