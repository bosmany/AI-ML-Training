import json
from datetime import timedelta

from freezegun import freeze_time
from helpers import NOW, inject_error

from lab import AuditConfig, run_audit, to_json, to_markdown


def cfg(**kw):
    return AuditConfig(now=NOW, sleep=lambda s: None, **kw)


def populate(ec2, s3, iam, ami):
    ec2.run_instances(ImageId=ami, MinCount=1, MaxCount=1)  # untagged
    sg = ec2.create_security_group(GroupName="open", Description="d")["GroupId"]
    ec2.authorize_security_group_ingress(GroupId=sg, IpPermissions=[
        {"IpProtocol": "tcp", "FromPort": 22, "ToPort": 22, "IpRanges": [{"CidrIp": "0.0.0.0/0"}]}])
    s3.create_bucket(Bucket="report-bucket")
    iam.create_user(UserName="frank")
    with freeze_time(NOW - timedelta(days=120)):
        iam.create_access_key(UserName="frank")
    return sg


def test_run_audit_combines_every_check_sorted_by_severity(ec2, s3, iam, ami):
    populate(ec2, s3, iam, ami)
    report = run_audit(ec2, s3, iam, cfg())
    checks = [f.check for f in report.findings]
    assert set(checks) == {"ec2-untagged", "sg-open-ingress", "s3-no-default-encryption",
                           "s3-no-public-access-block", "iam-no-mfa", "iam-old-access-key"}
    severities = [f.severity for f in report.findings]
    assert severities == sorted(severities, key={"high": 0, "medium": 1, "low": 2}.get), "high before medium before low"
    assert report.errors == [] and report.generated_at == NOW


def test_a_failing_service_becomes_an_error_entry_and_other_checks_still_run(ec2, s3, iam, ami):
    populate(ec2, s3, iam, ami)
    inject_error(iam, "iam.ListUsers", "AccessDenied", status=403)
    report = run_audit(ec2, s3, iam, cfg())
    assert [(e.check, e.code) for e in report.errors] == [("iam", "AccessDenied")]
    assert any(f.check == "sg-open-ingress" for f in report.findings), "one denied service must not hide the rest"
    assert not any(f.check.startswith("iam-") for f in report.findings)


def test_persistent_throttling_is_reported_after_retries_are_exhausted(ec2, s3, iam):
    inject_error(ec2, "ec2.DescribeSecurityGroups", "Throttling")
    sleeps: list[float] = []
    report = run_audit(ec2, s3, iam, AuditConfig(now=NOW, sleep=sleeps.append, max_attempts=3))
    assert [(e.check, e.code) for e in report.errors] == [("security-groups", "Throttling")]
    assert sleeps == [0.5, 1.0]


def test_to_json_has_summary_findings_and_errors(ec2, s3, iam, ami):
    populate(ec2, s3, iam, ami)
    doc = json.loads(to_json(run_audit(ec2, s3, iam, cfg())))
    assert doc["generated_at"] == NOW.isoformat()
    assert doc["summary"]["total"] == len(doc["findings"]) == 6
    assert doc["summary"]["by_severity"] == {"high": 4, "medium": 2}
    assert {"check", "resource", "severity", "message", "details"} <= set(doc["findings"][0])
    assert doc["errors"] == []
    assert to_json(run_audit(ec2, s3, iam, cfg())) == to_json(run_audit(ec2, s3, iam, cfg())), "output must be deterministic"


def test_to_markdown_renders_table_escapes_pipes_and_lists_errors(ec2, s3, iam):
    from lab import AuditError, AuditReport, Finding
    report = AuditReport(NOW, [Finding("x-check", "res|1", "high", "bad | thing\nnext line", {})],
                         [AuditError("iam", None, "AccessDenied", "nope")])
    md = to_markdown(report)
    assert md.startswith("# AWS audit report")
    assert "| Severity | Check | Resource | Message |" in md
    assert "res\\|1" in md and "bad \\| thing next line" in md, "pipes and newlines would break the table"
    assert "AccessDenied" in md and "Errors" in md
    empty = to_markdown(AuditReport(NOW, [], []))
    assert "No findings" in empty and "| Severity" not in empty
