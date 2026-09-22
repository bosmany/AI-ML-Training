"""Hermetic unit tests: no LocalStack container needed, these only construct objects/bytes.

Building a boto3 client and zipping a file never touch the network, so these run instantly even
under LAB_TARGET=starter (where they fail immediately with NotImplementedError, as they should).
"""
import io
import zipfile

from lab.client import make_clients
from lab.lambda_ import HANDLER, build_deployment_package


def test_make_clients_returns_the_three_services_pointed_at_the_endpoint(local_cfg):
    clients = make_clients(local_cfg)
    assert set(clients) == {"s3", "iam", "lambda"}
    for client in clients.values():
        assert client.meta.endpoint_url == local_cfg.endpoint_url
        assert client.meta.region_name == local_cfg.region


def test_make_clients_s3_uses_path_style_addressing(local_cfg):
    s3 = make_clients(local_cfg)["s3"]
    assert s3.meta.config.s3["addressing_style"] == "path"


def test_make_clients_works_with_no_aws_environment_at_all(local_cfg, monkeypatch):
    """It must never rely on ambient AWS_* env vars or a profile - only fake, explicit
    credentials it supplies itself - so construction must succeed even with none set."""
    for var in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_PROFILE", "AWS_SESSION_TOKEN"):
        monkeypatch.delenv(var, raising=False)
    clients = make_clients(local_cfg)
    frozen = clients["s3"]._get_credentials().get_frozen_credentials()
    assert frozen.access_key and frozen.secret_key


def test_build_deployment_package_produces_a_real_zip_with_handler_at_the_root(local_cfg):
    zip_bytes = build_deployment_package(local_cfg.handler_path)
    assert zip_bytes[:2] == b"PK", "not a real zip file"
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        assert zf.namelist() == ["handler.py"]
        source = zf.read("handler.py").decode()
    assert "def handler(event, context):" in source
    assert HANDLER == "handler.handler", "arcname must match the module.function HANDLER value"


def test_build_deployment_package_is_a_fresh_zip_each_call(local_cfg):
    first = build_deployment_package(local_cfg.handler_path)
    second = build_deployment_package(local_cfg.handler_path)
    assert first == second, "zipping the same source twice must be deterministic"
