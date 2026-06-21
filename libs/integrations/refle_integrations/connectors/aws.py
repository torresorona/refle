"""AWS connector — collects IAM/S3 posture via boto3; tests are pure functions.

collect() needs real AWS credentials and is best-effort (each section is guarded);
the test functions below are pure and unit-tested with synthetic resources.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from refle_integrations.base import ControlTest, Resource, TestResult


def _of_kind(resources: Sequence[Resource], kind: str) -> list[Resource]:
    return [r for r in resources if r.kind == kind]


def iam_mfa(resources: Sequence[Resource]) -> TestResult:
    users = _of_kind(resources, "iam_user")
    bad = [u.external_id for u in users if not u.data.get("mfa_enabled")]
    if bad:
        return TestResult(False, f"IAM users without MFA: {', '.join(bad)}")
    return TestResult(True, f"All {len(users)} IAM users have MFA")


def s3_public(resources: Sequence[Resource]) -> TestResult:
    public = [b.external_id for b in _of_kind(resources, "s3_bucket") if b.data.get("public")]
    if public:
        return TestResult(False, f"Public S3 buckets: {', '.join(public)}")
    return TestResult(True, "No public S3 buckets")


def s3_encryption(resources: Sequence[Resource]) -> TestResult:
    bad = [b.external_id for b in _of_kind(resources, "s3_bucket") if not b.data.get("encrypted")]
    if bad:
        return TestResult(False, f"Unencrypted S3 buckets: {', '.join(bad)}")
    return TestResult(True, "All S3 buckets encrypted")


class AWSConnector:
    key = "aws"
    name = "Amazon Web Services"
    description = "IAM MFA, S3 public-access and encryption checks."
    credential_fields = ["access_key_id", "secret_access_key", "region"]

    tests = [
        ControlTest("aws.iam.mfa", ["CC6.1"], "IAM users have MFA enabled", iam_mfa),
        ControlTest("aws.s3.public", ["CC6.6"], "No public S3 buckets", s3_public),
        ControlTest("aws.s3.encryption", ["CC6.7"], "S3 buckets encrypted", s3_encryption),
    ]

    def authenticate(self, credentials: dict[str, Any]) -> Any:
        import boto3

        return boto3.Session(
            aws_access_key_id=credentials.get("access_key_id"),
            aws_secret_access_key=credentials.get("secret_access_key"),
            region_name=credentials.get("region", "us-east-1"),
        )

    def collect(self, session: Any) -> list[Resource]:  # pragma: no cover - needs AWS
        resources: list[Resource] = []
        iam = session.client("iam")
        for user in iam.list_users().get("Users", []):
            name = user["UserName"]
            mfa = iam.list_mfa_devices(UserName=name).get("MFADevices", [])
            resources.append(Resource("iam_user", name, {"mfa_enabled": bool(mfa)}))

        s3 = session.client("s3")
        for bucket in s3.list_buckets().get("Buckets", []):
            name = bucket["Name"]
            public = False
            encrypted = False
            try:
                pab = s3.get_public_access_block(Bucket=name)["PublicAccessBlockConfiguration"]
                public = not pab.get("BlockPublicAcls", False)
            except Exception:
                public = True
            try:
                s3.get_bucket_encryption(Bucket=name)
                encrypted = True
            except Exception:
                encrypted = False
            resources.append(
                Resource("s3_bucket", name, {"public": public, "encrypted": encrypted})
            )
        return resources
