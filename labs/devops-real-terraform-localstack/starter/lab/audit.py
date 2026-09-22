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
    the SDK/backend version. Handle both instead of assuming one. Provided - no need to change."""
    if isinstance(document, dict):
        return document
    try:
        return json.loads(document)
    except json.JSONDecodeError:
        return json.loads(unquote(document))


def _statements(document: dict) -> list[dict]:
    """Normalize ``Statement`` to always be a list. Provided - no need to change."""
    stmts = document.get("Statement", [])
    return stmts if isinstance(stmts, list) else [stmts]


def _audit_bucket(s3, cfg: StackConfig) -> list[Finding]:
    """Real checks against the real bucket, same codes/severities as ``devops-aws-audit-moto``:

    - "s3-no-versioning" (medium): ``get_bucket_versioning`` Status is not ``"Enabled"``.
    - "s3-no-default-encryption" (high): ``get_bucket_encryption`` raises ``_NO_ENCRYPTION``.
      Any OTHER ``ClientError`` must propagate (do not swallow real errors).
    - "s3-no-public-access-block" (high): ``get_public_access_block`` raises ``_NO_PAB``
      (details ``{"missing": all four flags}``), OR any of the four flags in ``_PAB_FLAGS`` is
      false (details ``{"missing": [those flags]}``).
    """
    raise NotImplementedError


def _audit_role(iam, cfg: StackConfig) -> list[Finding]:
    """Real checks against the real role:

    - "iam-trust-policy-too-broad" (high): parse ``get_role(...)["Role"]["AssumeRolePolicyDocument"]``
      with ``_as_dict``; for any ``Allow`` statement whose ``Principal.Service`` includes anything
      other than ``"lambda.amazonaws.com"``, add a finding (details ``{"services": [...]}``).
    - "iam-wildcard-resource" (high): for every inline policy name from
      ``iam.list_role_policies(RoleName=cfg.role_name)["PolicyNames"]``, fetch its document with
      ``get_role_policy`` + ``_as_dict``; for any ``Allow`` statement whose ``Resource`` is (or
      includes) the literal string ``"*"``, add a finding named ``f"{role_name}/{policy_name}"``.
    """
    raise NotImplementedError


def _audit_function(lam, cfg: StackConfig) -> list[Finding]:
    """"lambda-not-active" (high): ``get_function(...)["Configuration"]["State"] != "Active"``."""
    raise NotImplementedError


def audit_stack(clients: dict[str, Any], cfg: StackConfig) -> list[Finding]:
    """Verify an already-applied stack for real, against the real LocalStack API: bucket
    hardening, IAM least privilege, and Lambda readiness. Concatenate ``_audit_bucket``,
    ``_audit_role`` and ``_audit_function``'s findings and return them; an empty list means the
    stack looks healthy.
    """
    raise NotImplementedError
