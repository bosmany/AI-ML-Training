"""Real integration tests for the "small Python verifier": run it against a correctly-applied
stack (must report nothing), then deliberately misconfigure the real resources and confirm the
audit catches each real problem."""
import json

import pytest

from lab.audit import audit_stack
from lab.client import make_clients
from lab.stack import apply_stack


@pytest.fixture
def applied(cfg):
    clients = make_clients(cfg)
    apply_stack(cfg, clients)
    return clients, cfg


def test_audit_of_a_correctly_applied_stack_has_no_findings(applied):
    clients, cfg = applied
    assert audit_stack(clients, cfg) == []


def test_audit_flags_a_bucket_with_no_public_access_block(applied):
    clients, cfg = applied
    clients["s3"].delete_public_access_block(Bucket=cfg.bucket_name)

    findings = audit_stack(clients, cfg)

    assert any(f.check == "s3-no-public-access-block" for f in findings)
    others = [f for f in findings if f.check == "s3-no-public-access-block"]
    assert set(others[0].details["missing"]) == {
        "BlockPublicAcls", "IgnorePublicAcls", "BlockPublicPolicy", "RestrictPublicBuckets",
    }


def test_audit_flags_a_bucket_with_versioning_suspended(applied):
    clients, cfg = applied
    clients["s3"].put_bucket_versioning(
        Bucket=cfg.bucket_name, VersioningConfiguration={"Status": "Suspended"}
    )

    findings = audit_stack(clients, cfg)

    assert any(f.check == "s3-no-versioning" and f.severity == "medium" for f in findings)


def test_audit_flags_an_iam_policy_with_a_wildcard_resource(applied):
    clients, cfg = applied
    wildcard_policy = {
        "Version": "2012-10-17",
        "Statement": [{"Effect": "Allow", "Action": "s3:*", "Resource": "*"}],
    }
    clients["iam"].put_role_policy(
        RoleName=cfg.role_name,
        PolicyName=cfg.policy_name,
        PolicyDocument=json.dumps(wildcard_policy),
    )

    findings = audit_stack(clients, cfg)

    assert any(f.check == "iam-wildcard-resource" for f in findings)


def test_audit_flags_a_trust_policy_broader_than_lambda_only(applied):
    clients, cfg = applied
    broad_trust = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"Service": ["lambda.amazonaws.com", "ec2.amazonaws.com"]},
                "Action": "sts:AssumeRole",
            }
        ],
    }
    clients["iam"].update_assume_role_policy(
        RoleName=cfg.role_name, PolicyDocument=json.dumps(broad_trust)
    )

    findings = audit_stack(clients, cfg)

    assert any(f.check == "iam-trust-policy-too-broad" for f in findings)
