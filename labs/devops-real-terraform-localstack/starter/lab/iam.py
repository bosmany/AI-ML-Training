"""The IAM half of the stack: a role only lambda.amazonaws.com can assume, with an inline
policy scoped to exactly this stack's bucket - no ``Resource: "*"`` anywhere."""
from __future__ import annotations

import json

from botocore.exceptions import ClientError

from .models import StackConfig

TRUST_POLICY = {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Principal": {"Service": "lambda.amazonaws.com"},
            "Action": "sts:AssumeRole",
        }
    ],
}


def _permissions_policy(cfg: StackConfig) -> dict:
    """Build the least-privilege inline policy document for this stack's role.

    Two statements: CloudWatch Logs (CreateLogGroup/CreateLogStream/PutLogEvents on
    ``arn:aws:logs:*:*:*`` - logs has no per-function ARN to scope to any tighter here), and
    S3 (GetObject/PutObject) scoped to ``f"arn:aws:s3:::{cfg.bucket_name}/*"`` only - never "*".
    """
    raise NotImplementedError


def ensure_lambda_role(iam, cfg: StackConfig) -> str:
    """Create ``cfg.role_name`` (trust policy: only ``lambda.amazonaws.com`` may assume it) and
    attach/replace its inline policy (``cfg.policy_name``) with ``_permissions_policy(cfg)``.
    Idempotent: re-running with the same config must not raise or duplicate anything.
    Returns the role ARN.

    Steps:
      1. ``iam.create_role(RoleName=cfg.role_name, AssumeRolePolicyDocument=json.dumps(TRUST_POLICY))``.
         Catch ``ClientError`` with code ``EntityAlreadyExists`` and fall back to
         ``iam.get_role(RoleName=cfg.role_name)`` instead of raising.
      2. ``iam.put_role_policy(...)`` with ``_permissions_policy(cfg)`` - this call is already an
         upsert, so calling it again just replaces the document in place.
    """
    raise NotImplementedError
