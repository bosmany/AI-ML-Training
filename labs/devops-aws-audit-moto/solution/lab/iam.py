"""IAM checks: users without MFA, active access keys that are too old."""
from __future__ import annotations

from datetime import timedelta

from botocore.exceptions import ClientError

from .client import error_code, list_all
from .models import AuditConfig, AuditError, AuditResult, Finding


def audit_iam(iam, cfg: AuditConfig) -> AuditResult:
    result = AuditResult()
    kw = {"page_size": cfg.page_size, "max_attempts": cfg.max_attempts, "sleep": cfg.sleep}
    users = list_all(iam, "list_users", "Users", **kw)
    for user in sorted(u["UserName"] for u in users):
        try:
            devices = list_all(iam, "list_mfa_devices", "MFADevices", params={"UserName": user}, **kw)
            if not devices:
                result.findings.append(Finding(
                    "iam-no-mfa", user, "medium", f"IAM user {user} has no MFA device", {},
                ))
            keys = list_all(iam, "list_access_keys", "AccessKeyMetadata", params={"UserName": user}, **kw)
        except ClientError as exc:
            result.errors.append(AuditError("iam-user", user, error_code(exc), str(exc)))
            continue
        for key in keys:
            age = cfg.now - key["CreateDate"]
            if key["Status"] == "Active" and age > timedelta(days=cfg.key_max_age_days):
                result.findings.append(Finding(
                    "iam-old-access-key", f"{user}/{key['AccessKeyId']}", "high",
                    f"Access key {key['AccessKeyId']} of {user} is {age.days} days old (limit {cfg.key_max_age_days})",
                    {"user": user, "access_key_id": key["AccessKeyId"], "age_days": age.days},
                ))
    return result
