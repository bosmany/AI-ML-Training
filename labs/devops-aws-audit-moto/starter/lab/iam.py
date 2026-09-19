"""IAM checks: users without MFA, active access keys that are too old."""
from __future__ import annotations

from .models import AuditConfig, AuditResult


def audit_iam(iam, cfg: AuditConfig) -> AuditResult:
    """For every user (``list_all("list_users", "Users")``, visited in name order):

    - "iam-no-mfa" (medium): no devices from ``list_mfa_devices`` (paginated too; pass params={"UserName": ...}).
    - "iam-old-access-key" (high): an ACTIVE key from ``list_access_keys`` (result key "AccessKeyMetadata")
      whose age ``cfg.now - CreateDate`` is STRICTLY greater than ``cfg.key_max_age_days``.
      resource = "<user>/<AccessKeyId>", details={"user", "access_key_id", "age_days"}.

    If a per-user call fails with a ClientError, record ``AuditError("iam-user", user, code, message)``
    and carry on with the next user.
    """
    raise NotImplementedError
