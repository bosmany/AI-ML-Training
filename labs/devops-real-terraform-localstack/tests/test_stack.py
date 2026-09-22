"""Real integration tests: these stand up a real LocalStack container (session fixture in
conftest.py) and create a real S3 bucket, IAM role+policy and Lambda function against it -
the same three resources ``terraform/main.tf`` declares, applied here with boto3 instead of
`terraform apply` because the terraform binary is not assumed to be installed (see README)."""
import json

import pytest

from lab.client import make_clients
from lab.stack import apply_stack


@pytest.fixture
def clients(cfg):
    return make_clients(cfg)


def test_apply_stack_creates_a_working_bucket_role_and_lambda(cfg, clients):
    outputs = apply_stack(cfg, clients)

    assert outputs.bucket_arn == f"arn:aws:s3:::{cfg.bucket_name}"
    assert outputs.role_arn == f"arn:aws:iam::000000000000:role/{cfg.role_name}"
    assert outputs.function_arn.endswith(f":function:{cfg.function_name}")

    versioning = clients["s3"].get_bucket_versioning(Bucket=cfg.bucket_name)
    assert versioning.get("Status") == "Enabled"

    encryption = clients["s3"].get_bucket_encryption(Bucket=cfg.bucket_name)
    rule = encryption["ServerSideEncryptionConfiguration"]["Rules"][0]
    assert rule["ApplyServerSideEncryptionByDefault"]["SSEAlgorithm"] == "AES256"

    pab = clients["s3"].get_public_access_block(Bucket=cfg.bucket_name)
    assert all(pab["PublicAccessBlockConfiguration"].values())

    role_policies = clients["iam"].list_role_policies(RoleName=cfg.role_name)["PolicyNames"]
    assert cfg.policy_name in role_policies
    doc = clients["iam"].get_role_policy(RoleName=cfg.role_name, PolicyName=cfg.policy_name)
    resources = [
        r
        for stmt in doc["PolicyDocument"]["Statement"]
        for r in ([stmt["Resource"]] if isinstance(stmt["Resource"], str) else stmt["Resource"])
    ]
    assert "*" not in resources, "the inline policy must be scoped, never a bare wildcard"

    function = clients["lambda"].get_function(FunctionName=cfg.function_name)["Configuration"]
    assert function["State"] == "Active"
    assert function["Runtime"] == "python3.12"

    result = clients["lambda"].invoke(
        FunctionName=cfg.function_name, Payload=json.dumps({"text": "hello localstack"}).encode()
    )
    payload = json.loads(result["Payload"].read())
    assert result["StatusCode"] == 200
    assert not result.get("FunctionError")
    assert payload == {
        "original": "hello localstack",
        "upper": "HELLO LOCALSTACK",
        "length": 16,
        "bucket": cfg.bucket_name,
    }


def test_apply_stack_is_idempotent(cfg, clients):
    first = apply_stack(cfg, clients)
    second = apply_stack(cfg, clients)  # re-apply, like `terraform apply` with no diff

    assert first == second

    buckets = clients["s3"].list_buckets()["Buckets"]
    assert sum(1 for b in buckets if b["Name"] == cfg.bucket_name) == 1

    functions = clients["lambda"].list_functions()["Functions"]
    assert sum(1 for f in functions if f["FunctionName"] == cfg.function_name) == 1

    roles = clients["iam"].list_roles()["Roles"]
    assert sum(1 for r in roles if r["RoleName"] == cfg.role_name) == 1

    # the function must still be invokable after a re-apply (no half-updated state)
    result = clients["lambda"].invoke(
        FunctionName=cfg.function_name, Payload=json.dumps({"text": "still works"}).encode()
    )
    assert json.loads(result["Payload"].read())["upper"] == "STILL WORKS"
