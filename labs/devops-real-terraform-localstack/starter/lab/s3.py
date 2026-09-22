"""The bucket half of the stack: create it, and converge it to the hardened settings
``terraform/main.tf`` declares (versioning, default encryption, full public access block)."""
from __future__ import annotations

from botocore.exceptions import ClientError

from .models import StackConfig

_PAB_FLAGS = ("BlockPublicAcls", "IgnorePublicAcls", "BlockPublicPolicy", "RestrictPublicBuckets")


def ensure_bucket(s3, cfg: StackConfig) -> str:
    """Create ``cfg.bucket_name`` if it does not already exist, then converge its settings.

    Idempotent like ``terraform apply``: calling this twice with the same config must not raise
    and must leave the bucket in the same state. Returns the bucket ARN
    (``f"arn:aws:s3:::{cfg.bucket_name}"``).

    Steps:
      1. ``s3.head_bucket(Bucket=...)``; on ``ClientError`` (not found), ``create_bucket``.
         Do NOT pass ``CreateBucketConfiguration`` - this lab only targets us-east-1, where a
         location constraint is invalid.
      2. ``put_bucket_versioning`` with ``VersioningConfiguration={"Status": "Enabled"}``.
      3. ``put_bucket_encryption`` with a single AES256 default-encryption rule.
      4. ``put_public_access_block`` with all four flags in ``_PAB_FLAGS`` set to ``True``.
    """
    raise NotImplementedError
