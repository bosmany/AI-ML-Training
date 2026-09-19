from datetime import timedelta

from freezegun import freeze_time
from helpers import NOW, Sleeper, inject_error

from lab import AuditConfig, audit_iam, audit_s3


def cfg(**kw):
    return AuditConfig(now=NOW, sleep=lambda s: None, **kw)


def names(result, check):
    return sorted(f.resource for f in result.findings if f.check == check)


# ---------------------------------------------------------------- S3
def test_bucket_without_default_encryption_is_flagged(s3):
    s3.create_bucket(Bucket="plain-bucket")
    s3.create_bucket(Bucket="secure-bucket")
    s3.put_bucket_encryption(Bucket="secure-bucket", ServerSideEncryptionConfiguration={
        "Rules": [{"ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}}]})
    assert names(audit_s3(s3, cfg()), "s3-no-default-encryption") == ["plain-bucket"]


def test_missing_public_access_block_and_partial_block_are_flagged(s3):
    for b in ("no-pab", "partial-pab", "full-pab"):
        s3.create_bucket(Bucket=b)
    flags = dict(BlockPublicAcls=True, IgnorePublicAcls=True, BlockPublicPolicy=True, RestrictPublicBuckets=True)
    s3.put_public_access_block(Bucket="full-pab", PublicAccessBlockConfiguration=flags)
    s3.put_public_access_block(Bucket="partial-pab", PublicAccessBlockConfiguration={**flags, "BlockPublicPolicy": False})
    result = audit_s3(s3, cfg())
    assert names(result, "s3-no-public-access-block") == ["no-pab", "partial-pab"]
    partial = next(f for f in result.findings if f.resource == "partial-pab" and f.check == "s3-no-public-access-block")
    assert partial.details["missing"] == ["BlockPublicPolicy"]


def test_no_buckets_is_not_an_error_and_a_hardened_bucket_has_no_findings(s3):
    empty = audit_s3(s3, cfg())
    assert empty.findings == [] and empty.errors == []
    s3.create_bucket(Bucket="hardened")
    s3.put_bucket_encryption(Bucket="hardened", ServerSideEncryptionConfiguration={
        "Rules": [{"ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "aws:kms"}}]})
    s3.put_public_access_block(Bucket="hardened", PublicAccessBlockConfiguration=dict(
        BlockPublicAcls=True, IgnorePublicAcls=True, BlockPublicPolicy=True, RestrictPublicBuckets=True))
    result = audit_s3(s3, cfg())
    assert result.findings == [] and result.errors == []


def test_access_denied_on_one_check_is_recorded_and_other_checks_still_run(s3):
    s3.create_bucket(Bucket="locked-bucket")
    inject_error(s3, "s3.GetBucketEncryption", "AccessDenied", status=403)
    sleeper = Sleeper()
    result = audit_s3(s3, AuditConfig(now=NOW, sleep=sleeper))
    assert [(e.check, e.resource, e.code) for e in result.errors] == [("s3-no-default-encryption", "locked-bucket", "AccessDenied")]
    assert names(result, "s3-no-public-access-block") == ["locked-bucket"], "the PAB check must still run"
    assert sleeper.delays == [], "AccessDenied is not retried"


def test_access_denied_on_public_access_block_is_an_error_not_a_finding(s3):
    s3.create_bucket(Bucket="pab-denied")
    inject_error(s3, "s3.GetPublicAccessBlock", "AccessDenied", status=403)
    result = audit_s3(s3, cfg())
    assert [(e.check, e.code) for e in result.errors] == [("s3-no-public-access-block", "AccessDenied")]
    assert names(result, "s3-no-public-access-block") == [], "we could not look, so we must not claim it is unprotected"
    assert names(result, "s3-no-default-encryption") == ["pab-denied"]


def test_throttled_s3_call_is_retried_with_backoff(s3):
    s3.create_bucket(Bucket="busy-bucket")
    inject_error(s3, "s3.GetPublicAccessBlock", "SlowDown", times=2, status=503)
    sleeper = Sleeper()
    result = audit_s3(s3, AuditConfig(now=NOW, sleep=sleeper))
    assert names(result, "s3-no-public-access-block") == ["busy-bucket"] and result.errors == []
    assert sleeper.delays == [0.5, 1.0]


# ---------------------------------------------------------------- IAM
def test_user_without_mfa_is_flagged_and_user_with_mfa_is_not(iam):
    iam.create_user(UserName="alice")
    iam.create_user(UserName="bob")
    dev = iam.create_virtual_mfa_device(VirtualMFADeviceName="bob-mfa")["VirtualMFADevice"]
    iam.enable_mfa_device(UserName="bob", SerialNumber=dev["SerialNumber"],
                          AuthenticationCode1="123456", AuthenticationCode2="654321")
    assert names(audit_iam(iam, cfg()), "iam-no-mfa") == ["alice"]


def test_access_key_age_boundary_is_strictly_greater_than_the_limit(iam):
    for user, age in (("exact", 90), ("over", 91), ("young", 5)):
        iam.create_user(UserName=user)
        with freeze_time(NOW - timedelta(days=age)):
            iam.create_access_key(UserName=user)
    result = audit_iam(iam, cfg(key_max_age_days=90))
    assert [f.details["user"] for f in result.findings if f.check == "iam-old-access-key"] == ["over"]
    old = next(f for f in result.findings if f.check == "iam-old-access-key")
    assert old.details["age_days"] == 91 and old.resource.startswith("over/AKIA")


def test_inactive_old_key_is_ignored_and_a_second_old_key_is_reported(iam):
    iam.create_user(UserName="carol")
    with freeze_time(NOW - timedelta(days=200)):
        retired = iam.create_access_key(UserName="carol")["AccessKey"]["AccessKeyId"]
        active = iam.create_access_key(UserName="carol")["AccessKey"]["AccessKeyId"]
    iam.update_access_key(UserName="carol", AccessKeyId=retired, Status="Inactive")
    keys = [f.details["access_key_id"] for f in audit_iam(iam, cfg()).findings if f.check == "iam-old-access-key"]
    assert keys == [active], "only ACTIVE keys older than the limit are a finding"


def test_access_denied_for_one_user_is_reported_and_other_users_are_still_audited(iam):
    iam.create_user(UserName="dave")
    iam.create_user(UserName="erin")
    state = {"n": 0}
    from types import SimpleNamespace

    def deny_first_user(**_):
        state["n"] += 1
        if state["n"] == 1:
            return SimpleNamespace(status_code=403, headers={}, content=b""), {"Error": {"Code": "AccessDenied", "Message": "no"}}

    iam.meta.events.register("before-call.iam.ListMFADevices", deny_first_user)
    result = audit_iam(iam, cfg())
    assert [(e.resource, e.code) for e in result.errors] == [("dave", "AccessDenied")]
    assert names(result, "iam-no-mfa") == ["erin"]
