"""The one real Lambda handler this lab deploys two different ways: once by Terraform
(``terraform/main.tf``'s ``archive_file`` data source zips this exact file) and once by the
Python provisioner the learner writes (``lab/lambda_.py``'s ``build_deployment_package`` zips
this same file). Both paths must produce a working, identical function.

Deliberately has NO third-party imports and makes NO network calls of its own (no boto3 call
from inside the function): a real Lambda invocation against LocalStack already has to cross
a container boundary, and keeping the function pure keeps that invocation fast and deterministic.
"""
from __future__ import annotations

import os


def handler(event, context):
    text = event.get("text", "")
    return {
        "original": text,
        "upper": text.upper(),
        "length": len(text),
        "bucket": os.environ.get("BUCKET_NAME", ""),
    }
