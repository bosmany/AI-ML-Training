"""The bucket half of the stack: create it, and converge it to the hardened settings
``terraform/main.tf`` declares (versioning, default encryption, full public access block)."""
from __future__ import annotations

from botocore.exceptions import ClientError

from .models import StackConfig

_PAB_FLAGS = ("BlockPublicAcls", "IgnorePublicAcls", "BlockPublicPolicy", "RestrictPublicBuckets")


def ensure_bucket(s3, cfg: StackConfig) -> str:
    """Create ``cfg.bucket_name`` if it does not already exist, then converge its settings.

    Idempotent like ``terraform apply``: calling this twice with the same config must not raise
    and must leave the bucket in the same state. Returns the bucket ARN.
    """
    try:
        s3.head_bucket(Bucket=cfg.bucket_name)
    except ClientError:
        # us-east-1 is the one region that must NOT pass CreateBucketConfiguration; LocalStack
        # follows the same real-AWS quirk, so this only ever creates in us-east-1 style.
        s3.create_bucket(Bucket=cfg.bucket_name)

    s3.put_bucket_versioning(
        Bucket=cfg.bucket_name, VersioningConfiguration={"Status": "Enabled"}
    )
    s3.put_bucket_encryption(
        Bucket=cfg.bucket_name,
        ServerSideEncryptionConfiguration={
            "Rules": [{"ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}}]
        },
    )
    s3.put_public_access_block(
        Bucket=cfg.bucket_name,
        PublicAccessBlockConfiguration={flag: True for flag in _PAB_FLAGS},
    )
    return f"arn:aws:s3:::{cfg.bucket_name}"
