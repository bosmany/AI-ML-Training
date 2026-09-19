"""S3 checks: default encryption and public access block."""
from __future__ import annotations

from .models import AuditConfig, AuditResult

# Error codes that mean "not configured" (this is a FINDING, not a failure):
_NO_ENCRYPTION = "ServerSideEncryptionConfigurationNotFoundError"
_NO_PAB = "NoSuchPublicAccessBlockConfiguration"
_PAB_FLAGS = ("BlockPublicAcls", "IgnorePublicAcls", "BlockPublicPolicy", "RestrictPublicBuckets")


def audit_s3(s3, cfg: AuditConfig) -> AuditResult:
    """For every bucket (list with ``list_all("list_buckets", "Buckets")``, visit in name order):

    - "s3-no-default-encryption" (high): ``get_bucket_encryption`` raises ``_NO_ENCRYPTION``.
    - "s3-no-public-access-block" (high): ``get_public_access_block`` raises ``_NO_PAB`` (details
      {"missing": all four flags}) OR any of the four flags is False (details {"missing": [those flags]}).

    Wrap every per-bucket call in ``retry_call`` (cfg.max_attempts, cfg.sleep). Any OTHER ClientError
    (e.g. AccessDenied) for a bucket becomes an ``AuditError(check, bucket, code, message)`` in
    ``result.errors`` - and the remaining checks/buckets still run.
    """
    raise NotImplementedError
