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
    """Zip ``handler_path`` into an in-memory Lambda deployment package (return the raw bytes,
    not a file on disk).

    Use ``io.BytesIO()`` + ``zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED)``
    and ``zf.write(handler_path, arcname="handler.py")`` - the arcname (not the source path) is
    what determines the importable module name inside Lambda, and it must match ``HANDLER`` above.
    """
    raise NotImplementedError


def _wait_until_ready(lambda_client, function_name: str, timeout: float = 60.0) -> dict:
    """Poll ``lambda_client.get_function(FunctionName=function_name)["Configuration"]`` until
    ``State == "Active"`` and ``LastUpdateStatus == "Successful"`` (default that field to
    ``"Successful"`` if it is absent - some backends omit it on a fresh create). Sleep briefly
    between polls (e.g. 1s). Raise ``RuntimeError`` if either field is ``"Failed"``, and
    ``TimeoutError`` if ``timeout`` seconds pass without becoming ready.

    Why this matters: function creation and code updates are asynchronous even against
    LocalStack; invoking a function whose state is still ``Pending`` raises
    ``ResourceConflictException``.
    """
    raise NotImplementedError


def ensure_function(lambda_client, cfg: StackConfig, role_arn: str, zip_bytes: bytes) -> str:
    """Create ``cfg.function_name`` if missing, else update its code - idempotent, like
    ``terraform apply`` re-applying an ``aws_lambda_function`` resource. Wait for the function to
    be ready (``_wait_until_ready``) before returning. Returns the function ARN.

    Steps:
      1. Try ``lambda_client.create_function(FunctionName=cfg.function_name, Runtime=RUNTIME,
         Role=role_arn, Handler=HANDLER, Code={"ZipFile": zip_bytes},
         Environment={"Variables": {"BUCKET_NAME": cfg.bucket_name}}, Timeout=30)``.
      2. On ``ClientError`` with code ``ResourceConflictException`` (function already exists),
         call ``update_function_code`` with the new zip, then call ``_wait_until_ready`` again
         right there before doing anything else - a function can only have one update in flight
         at a time, so starting ``update_function_configuration`` while the code update is still
         in progress raises its own ``ResourceConflictException`` ("An update is in progress").
         Once that settles, call ``update_function_configuration`` to refresh
         ``Role``/``Environment``, then look up the current ``FunctionArn`` with ``get_function``.
      3. Either way, call ``_wait_until_ready`` once more before returning the ARN.
    """
    raise NotImplementedError


def invoke(lambda_client, function_name: str, payload: dict) -> dict:
    """Synchronously invoke ``function_name`` with a JSON ``payload`` and return the decoded
    JSON response body. Raise ``RuntimeError`` if the function itself raised
    (``response.get("FunctionError")`` is truthy) - never silently return a partial/error body
    as if it were a normal result.
    """
    raise NotImplementedError
