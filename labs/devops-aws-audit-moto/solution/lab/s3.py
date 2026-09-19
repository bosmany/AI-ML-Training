"""S3 checks: default encryption and public access block."""
from __future__ import annotations

from botocore.exceptions import ClientError

from .client import error_code, list_all, retry_call
from .models import AuditConfig, AuditError, AuditResult, Finding

_NO_ENCRYPTION = "ServerSideEncryptionConfigurationNotFoundError"
_NO_PAB = "NoSuchPublicAccessBlockConfiguration"
_PAB_FLAGS = ("BlockPublicAcls", "IgnorePublicAcls", "BlockPublicPolicy", "RestrictPublicBuckets")


def audit_s3(s3, cfg: AuditConfig) -> AuditResult:
    result = AuditResult()
    buckets = list_all(s3, "list_buckets", "Buckets",
                       page_size=cfg.page_size, max_attempts=cfg.max_attempts, sleep=cfg.sleep)
    for name in sorted(b["Name"] for b in buckets):
        # --- default encryption
        try:
            retry_call(lambda: s3.get_bucket_encryption(Bucket=name), max_attempts=cfg.max_attempts, sleep=cfg.sleep)
        except ClientError as exc:
            if error_code(exc) == _NO_ENCRYPTION:
                result.findings.append(Finding(
                    "s3-no-default-encryption", name, "high",
                    f"Bucket {name} has no default encryption configuration", {},
                ))
            else:
                result.errors.append(AuditError("s3-no-default-encryption", name, error_code(exc), str(exc)))
        # --- public access block
        try:
            resp = retry_call(lambda: s3.get_public_access_block(Bucket=name),
                              max_attempts=cfg.max_attempts, sleep=cfg.sleep)
            conf = resp["PublicAccessBlockConfiguration"]
            missing = [f for f in _PAB_FLAGS if not conf.get(f)]
            if missing:
                result.findings.append(Finding(
                    "s3-no-public-access-block", name, "high",
                    f"Bucket {name} public access block is incomplete: {', '.join(missing)} not enabled",
                    {"missing": missing},
                ))
        except ClientError as exc:
            if error_code(exc) == _NO_PAB:
                result.findings.append(Finding(
                    "s3-no-public-access-block", name, "high",
                    f"Bucket {name} has no public access block", {"missing": list(_PAB_FLAGS)},
                ))
            else:
                result.errors.append(AuditError("s3-no-public-access-block", name, error_code(exc), str(exc)))
    return result
