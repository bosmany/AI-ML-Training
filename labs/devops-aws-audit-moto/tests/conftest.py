"""Pick which implementation the tests import as ``lab``.

Learners run ``pytest`` (target = starter). Maintainers/CI run ``LAB_TARGET=solution pytest``.
"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True

_TARGET = os.environ.get("LAB_TARGET", "starter")
_LAB_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_LAB_DIR / _TARGET))

import boto3  # noqa: E402  (after sys.path setup)
import pytest  # noqa: E402
from moto import mock_aws  # noqa: E402

FAKE_ENV = {
    "AWS_ACCESS_KEY_ID": "testing",
    "AWS_SECRET_ACCESS_KEY": "testing",
    "AWS_SECURITY_TOKEN": "testing",
    "AWS_SESSION_TOKEN": "testing",
    "AWS_DEFAULT_REGION": "us-east-1",
    "AWS_EC2_METADATA_DISABLED": "true",
}


@pytest.fixture(autouse=True)
def _fake_aws_environment(monkeypatch, tmp_path):
    """Make it impossible to reach a real AWS account, whatever the developer's machine has configured."""
    for var in ("AWS_PROFILE", "AWS_ENDPOINT_URL", "AWS_ENDPOINT_URL_S3", "AWS_ENDPOINT_URL_EC2",
                "AWS_ENDPOINT_URL_IAM", "AWS_ROLE_ARN", "AWS_WEB_IDENTITY_TOKEN_FILE"):
        monkeypatch.delenv(var, raising=False)
    for key, value in FAKE_ENV.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv("AWS_CONFIG_FILE", str(tmp_path / "no-such-config"))
    monkeypatch.setenv("AWS_SHARED_CREDENTIALS_FILE", str(tmp_path / "no-such-credentials"))
    yield


@pytest.fixture(autouse=True)
def _moto(_fake_aws_environment):
    with mock_aws():
        yield


@pytest.fixture
def ec2():
    return boto3.client("ec2", region_name="us-east-1")


@pytest.fixture
def s3():
    return boto3.client("s3", region_name="us-east-1")


@pytest.fixture
def iam():
    return boto3.client("iam", region_name="us-east-1")


@pytest.fixture
def ami():
    # moto accepts any well-formed AMI id; looking up its bundled image catalogue costs ~0.5 s per test.
    return "ami-12345678"
