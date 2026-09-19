from datetime import datetime, timedelta, timezone

import pytest
from freezegun import freeze_time
from helpers import NOW, count_calls

from lab import AuditConfig, Finding, audit_ec2, stopped_at


def cfg(**kw):
    return AuditConfig(now=NOW, sleep=lambda s: None, **kw)


def launch(ec2, ami, tags=None, n=1):
    spec = [{"ResourceType": "instance", "Tags": [{"Key": k, "Value": v} for k, v in tags.items()]}] if tags else []
    r = ec2.run_instances(ImageId=ami, MinCount=n, MaxCount=n, TagSpecifications=spec)
    return [i["InstanceId"] for i in r["Instances"]]


def checks(result, check):
    return sorted(f.resource for f in result.findings if f.check == check)


def test_untagged_instance_is_flagged_and_tagged_one_is_not(ec2, ami):
    (bad,) = launch(ec2, ami)
    (good,) = launch(ec2, ami, {"Owner": "team-a"})
    result = audit_ec2(ec2, cfg())
    assert checks(result, "ec2-untagged") == [bad]
    finding = next(f for f in result.findings if f.resource == bad)
    assert isinstance(finding, Finding) and finding.details["missing_tags"] == ["Owner"]
    assert good not in [f.resource for f in result.findings]


def test_empty_tag_value_and_extra_required_tags_count_as_missing(ec2, ami):
    (blank,) = launch(ec2, ami, {"Owner": ""})
    (partial,) = launch(ec2, ami, {"Owner": "x"})
    result = audit_ec2(ec2, cfg(required_tags=("Owner", "CostCenter")))
    assert checks(result, "ec2-untagged") == sorted([blank, partial])
    by_id = {f.resource: f for f in result.findings}
    assert by_id[partial].details["missing_tags"] == ["CostCenter"]


def test_terminated_instances_are_ignored(ec2, ami):
    (gone,) = launch(ec2, ami)
    ec2.terminate_instances(InstanceIds=[gone])
    assert audit_ec2(ec2, cfg()).findings == []
    with freeze_time(NOW - timedelta(days=400)):
        launch(ec2, ami, {"Owner": "x"})  # launched long ago but still running: not "stopped"
    assert audit_ec2(ec2, cfg()).findings == [], "running instances are never stopped-too-long"


def test_stopped_at_parses_state_transition_reason():
    inst = {"StateTransitionReason": "User initiated (2024-01-01 12:00:00 GMT)"}
    assert stopped_at(inst) == datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)
    assert stopped_at({"StateTransitionReason": "UTC variant (2024-01-01 12:00:00 UTC)"}) is not None
    assert stopped_at({"StateTransitionReason": ""}) is None, "never-stopped instances have an empty reason"


def test_stopped_too_long_boundary_is_strictly_greater_than_the_limit(ec2, ami):
    tags = {"Owner": "x"}
    with freeze_time(NOW - timedelta(days=30)):  # exactly 30 days before "now"
        (edge,) = launch(ec2, ami, tags)
        ec2.stop_instances(InstanceIds=[edge])
    with freeze_time(NOW - timedelta(days=30, seconds=1)):
        (over,) = launch(ec2, ami, tags)
        ec2.stop_instances(InstanceIds=[over])
    with freeze_time(NOW - timedelta(days=2)):
        (recent,) = launch(ec2, ami, tags)
        ec2.stop_instances(InstanceIds=[recent])
    result = audit_ec2(ec2, cfg(stopped_max_days=30))
    assert checks(result, "ec2-stopped-too-long") == [over], "30d exactly is fine; 30d+1s is over the limit"
    assert next(f for f in result.findings if f.resource == over).details["stopped_days"] == 30


def test_audit_ec2_reads_every_page(ec2, ami):
    ids = [launch(ec2, ami)[0] for _ in range(12)]  # 12 reservations -> 3 pages of 5
    seen = count_calls(ec2, "ec2.DescribeInstances")
    result = audit_ec2(ec2, cfg(page_size=5))
    assert checks(result, "ec2-untagged") == sorted(ids), "instances on later pages must be audited too"
    assert seen["calls"] == 3


def test_naive_now_is_rejected(ec2):
    with pytest.raises(ValueError, match="timezone"):
        audit_ec2(ec2, AuditConfig(now=datetime(2024, 6, 1)))  # either the config or the audit may raise
