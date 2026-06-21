"""Object storage helper (S3 / MinIO) for evidence artifacts.

boto3 is synchronous; callers wrap these in ``run_in_threadpool`` from async paths.
"""

from __future__ import annotations

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError
from refle_core.config import get_settings


def _client():
    s = get_settings()
    return boto3.client(
        "s3",
        endpoint_url=s.s3_endpoint_url,
        aws_access_key_id=s.s3_access_key,
        aws_secret_access_key=s.s3_secret_key,
        config=Config(signature_version="s3v4"),
        region_name="us-east-1",
    )


def ensure_bucket() -> None:
    s = get_settings()
    client = _client()
    try:
        client.head_bucket(Bucket=s.s3_bucket)
    except ClientError:
        client.create_bucket(Bucket=s.s3_bucket)


def put_object(key: str, data: bytes, content_type: str | None) -> None:
    s = get_settings()
    _client().put_object(
        Bucket=s.s3_bucket,
        Key=key,
        Body=data,
        ContentType=content_type or "application/octet-stream",
    )


def get_object(key: str) -> bytes:
    s = get_settings()
    response = _client().get_object(Bucket=s.s3_bucket, Key=key)
    return response["Body"].read()


def presigned_get(key: str, expires: int = 3600) -> str:
    s = get_settings()
    return _client().generate_presigned_url(
        "get_object", Params={"Bucket": s.s3_bucket, "Key": key}, ExpiresIn=expires
    )


def delete_object(key: str) -> None:
    s = get_settings()
    _client().delete_object(Bucket=s.s3_bucket, Key=key)
