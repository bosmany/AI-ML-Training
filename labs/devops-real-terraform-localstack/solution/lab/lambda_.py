"""The Lambda half of the stack: build a real deployment package, create-or-update the real
function, and invoke it for real."""
from __future__ import annotations

import io
import json
import time
import zipfile
from pathlib import Path

from botocore.exceptions import ClientError

from .models import StackConfig

RUNTIME = "python3.12"
HANDLER = "handler.handler"  # module_name.function_name, matching the zip's arcname below


def build_deployment_package(handler_path: Path) -> bytes:
    """Zip ``handler_path`` into an in-memory Lambda deployment package.

    The file is stored as ``handler.py`` at the zip root (the arcname, not the source path) so
    the module import inside Lambda is ``handler`` regardless of where ``handler_path`` lives on
    disk - matching the ``handler.handler`` value of ``HANDLER`` above.
    """
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.write(handler_path, arcname="handler.py")
    return buffer.getvalue()


def _wait_until_ready(lambda_client, function_name: str, timeout: float = 60.0) -> dict:
    """Poll until the function is both ``Active`` and its last code update ``Successful``.

    Function creation and code updates are asynchronous even against LocalStack; a Lambda whose
    state is still ``Pending`` cannot be invoked yet (``ResourceConflictException``).
    """
    deadline = time.monotonic() + timeout
    last = None
    while time.monotonic() < deadline:
        last = lambda_client.get_function(FunctionName=function_name)["Configuration"]
        state = last.get("State")
        last_update = last.get("LastUpdateStatus", "Successful")
        if state == "Failed" or last_update == "Failed":
            raise RuntimeError(f"lambda {function_name} failed to become ready: {last}")
        if state == "Active" and last_update == "Successful":
            return last
        time.sleep(1)
    raise TimeoutError(f"lambda {function_name} did not become ready within {timeout}s: {last}")


def ensure_function(lambda_client, cfg: StackConfig, role_arn: str, zip_bytes: bytes) -> str:
    """Create ``cfg.function_name`` if missing, else update its code - idempotent, like
    ``terraform apply`` re-applying an ``aws_lambda_function`` resource. Waits for the function
    to be ready before returning. Returns the function ARN.
    """
    try:
        created = lambda_client.create_function(
            FunctionName=cfg.function_name,
            Runtime=RUNTIME,
            Role=role_arn,
            Handler=HANDLER,
            Code={"ZipFile": zip_bytes},
            Environment={"Variables": {"BUCKET_NAME": cfg.bucket_name}},
            Timeout=30,
        )
        function_arn = created["FunctionArn"]
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") != "ResourceConflictException":
            raise
        lambda_client.update_function_code(FunctionName=cfg.function_name, ZipFile=zip_bytes)
        # A function can only have one update in flight at a time: starting the configuration
        # update before the code update has finished raises ResourceConflictException ("An
        # update is in progress"), so wait for the code update to settle before starting the
        # next one.
        _wait_until_ready(lambda_client, cfg.function_name)
        lambda_client.update_function_configuration(
            FunctionName=cfg.function_name,
            Role=role_arn,
            Environment={"Variables": {"BUCKET_NAME": cfg.bucket_name}},
        )
        function_arn = lambda_client.get_function(FunctionName=cfg.function_name)[
            "Configuration"
        ]["FunctionArn"]

    _wait_until_ready(lambda_client, cfg.function_name)
    return function_arn


def invoke(lambda_client, function_name: str, payload: dict) -> dict:
    """Synchronously invoke ``function_name`` with a JSON ``payload`` and return the decoded
    JSON response. Raises ``RuntimeError`` if the function itself raised (``FunctionError``).
    """
    response = lambda_client.invoke(
        FunctionName=function_name,
        InvocationType="RequestResponse",
        Payload=json.dumps(payload).encode("utf-8"),
    )
    body = json.loads(response["Payload"].read())
    if response.get("FunctionError"):
        raise RuntimeError(f"lambda {function_name} raised: {body}")
    return body
