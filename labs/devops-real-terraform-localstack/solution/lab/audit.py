"""The "small Python verifier" the lab README talks about: the equivalent of running
``terraform show`` and eyeballing it, except it is a real, testable audit against the real
LocalStack API - same idea and ``Finding`` shape as ``labs/devops-aws-audit-moto``, applied to
one already-created stack instead of a whole account."""
from __future__ import annotations

import json
from typing import Any
from urllib.parse import unquote

from botocore.exceptions import ClientError

from .models import Finding, StackConfig

_NO_ENCRYPTION = "ServerSideEncryptionConfigurationNotFoundError"
_NO_PAB = "NoSuchPublicAccessBlockConfiguration"
_PAB_FLAGS = ("BlockPublicAcls", "IgnorePublicAcls", "BlockPublicPolicy", "RestrictPublicBuckets")


def _as_dict(document: Any) -> dict:
    """IAM policy documents come back either already-parsed or URL-encoded JSON, depending on
    the SDK/backend version. Handle both instead of assuming one."""
    if isinstance(document, dict):
        return document
    try:
        return json.loads(document)
    except json.JSONDecodeError:
        return json.loads(unquote(document))


def _statements(document: dict) -> list[dict]:
    stmts = document.get("Statement", [])
    return stmts if isinstance(stmts, list) else [stmts]


def _audit_bucket(s3, cfg: StackConfig) -> list[Finding]:
    findings: list[Finding] = []
    bucket = cfg.bucket_name

    versioning = s3.get_bucket_versioning(Bucket=bucket)
    if versioning.get("Status") != "Enabled":
        findings.append(Finding(
            "s3-no-versioning", bucket, "medium",
            f"Bucket {bucket} does not have versioning enabled", {},
        ))

    try:
        s3.get_bucket_encryption(Bucket=bucket)
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") == _NO_ENCRYPTION:
            findings.append(Finding(
                "s3-no-default-encryption", bucket, "high",
                f"Bucket {bucket} has no default encryption configuration", {},
            ))
        else:
            raise

    try:
        conf = s3.get_public_access_block(Bucket=bucket)["PublicAccessBlockConfiguration"]
        missing = [flag for flag in _PAB_FLAGS if not conf.get(flag)]
        if missing:
            findings.append(Finding(
                "s3-no-public-access-block", bucket, "high",
                f"Bucket {bucket} public access block is incomplete: {', '.join(missing)}",
                {"missing": missing},
            ))
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") == _NO_PAB:
            findings.append(Finding(
                "s3-no-public-access-block", bucket, "high",
                f"Bucket {bucket} has no public access block at all", {"missing": list(_PAB_FLAGS)},
            ))
        else:
            raise

    return findings


def _audit_role(iam, cfg: StackConfig) -> list[Finding]:
    findings: list[Finding] = []
    role_name = cfg.role_name

    role = iam.get_role(RoleName=role_name)["Role"]
    trust = _as_dict(role["AssumeRolePolicyDocument"])
    for stmt in _statements(trust):
        principal = stmt.get("Principal", {})
        services = principal.get("Service", [])
        services = [services] if isinstance(services, str) else services
        if stmt.get("Effect") == "Allow" and any(s != "lambda.amazonaws.com" for s in services):
            findings.append(Finding(
                "iam-trust-policy-too-broad", role_name, "high",
                f"Role {role_name} can be assumed by more than lambda.amazonaws.com: {services}",
                {"services": services},
            ))

    for policy_name in iam.list_role_policies(RoleName=role_name)["PolicyNames"]:
        doc = _as_dict(
            iam.get_role_policy(RoleName=role_name, PolicyName=policy_name)["PolicyDocument"]
        )
        for stmt in _statements(doc):
            if stmt.get("Effect") != "Allow":
                continue
            resources = stmt.get("Resource", [])
            resources = [resources] if isinstance(resources, str) else resources
            if any(r == "*" for r in resources):
                findings.append(Finding(
                    "iam-wildcard-resource", f"{role_name}/{policy_name}", "high",
                    f"Policy {policy_name} on role {role_name} grants access to Resource '*'",
                    {"statement_sid": stmt.get("Sid", "")},
                ))

    return findings


def _audit_function(lam, cfg: StackConfig) -> list[Finding]:
    config = lam.get_function(FunctionName=cfg.function_name)["Configuration"]
    if config.get("State") != "Active":
        return [Finding(
            "lambda-not-active", cfg.function_name, "high",
            f"Function {cfg.function_name} is not Active (state={config.get('State')})",
            {"state": config.get("State")},
        )]
    return []


def audit_stack(clients: dict[str, Any], cfg: StackConfig) -> list[Finding]:
    """Verify an already-applied stack for real, against the real LocalStack API: bucket
    hardening, IAM least privilege, and Lambda readiness. An empty list means the stack looks
    healthy; every entry is a real problem the checks actually found.
    """
    findings: list[Finding] = []
    findings.extend(_audit_bucket(clients["s3"], cfg))
    findings.extend(_audit_role(clients["iam"], cfg))
    findings.extend(_audit_function(clients["lambda"], cfg))
    return findings
