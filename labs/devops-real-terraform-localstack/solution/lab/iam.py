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
    return {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "WriteLogs",
                "Effect": "Allow",
                "Action": ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"],
                "Resource": "arn:aws:logs:*:*:*",
            },
            {
                "Sid": "ReadWriteOwnBucketOnly",
                "Effect": "Allow",
                "Action": ["s3:GetObject", "s3:PutObject"],
                "Resource": f"arn:aws:s3:::{cfg.bucket_name}/*",
            },
        ],
    }


def ensure_lambda_role(iam, cfg: StackConfig) -> str:
    """Create ``cfg.role_name`` (trust policy: only ``lambda.amazonaws.com`` may assume it) and
    attach/replace its inline policy (``cfg.policy_name``) with the least-privilege document
    above. Idempotent: re-running with the same config must not raise or duplicate anything.
    Returns the role ARN.
    """
    try:
        role = iam.create_role(
            RoleName=cfg.role_name, AssumeRolePolicyDocument=json.dumps(TRUST_POLICY)
        )["Role"]
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") != "EntityAlreadyExists":
            raise
        role = iam.get_role(RoleName=cfg.role_name)["Role"]

    # put_role_policy is already an upsert: re-running replaces the document in place.
    iam.put_role_policy(
        RoleName=cfg.role_name,
        PolicyName=cfg.policy_name,
        PolicyDocument=json.dumps(_permissions_policy(cfg)),
    )
    return role["Arn"]
