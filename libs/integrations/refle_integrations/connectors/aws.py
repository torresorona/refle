"""AWS connector — collects IAM/S3/CloudTrail posture via boto3; tests are pure.

collect() needs real AWS credentials and is best-effort (each section is guarded);
the test functions below are pure and unit-tested with synthetic resources.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from refle_integrations.base import ControlTest, Resource, TestResult

# Baselines for the password-policy check (CIS-aligned).
_MIN_PASSWORD_LENGTH = 14


def _of_kind(resources: Sequence[Resource], kind: str) -> list[Resource]:
    return [r for r in resources if r.kind == kind]


def iam_mfa(resources: Sequence[Resource]) -> TestResult:
    users = _of_kind(resources, "iam_user")
    bad = [u.external_id for u in users if not u.data.get("mfa_enabled")]
    if bad:
        return TestResult(False, f"IAM users without MFA: {', '.join(bad)}")
    return TestResult(True, f"All {len(users)} IAM users have MFA")


def iam_password_policy(resources: Sequence[Resource]) -> TestResult:
    policies = _of_kind(resources, "iam_password_policy")
    if not policies:
        return TestResult(False, "No IAM account password policy is configured")
    p = policies[0].data
    problems = []
    if (p.get("minimum_length") or 0) < _MIN_PASSWORD_LENGTH:
        problems.append(f"min length < {_MIN_PASSWORD_LENGTH}")
    if not p.get("require_symbols"):
        problems.append("symbols not required")
    if not p.get("require_numbers"):
        problems.append("numbers not required")
    if problems:
        return TestResult(False, f"Weak IAM password policy: {', '.join(problems)}")
    return TestResult(True, "IAM password policy meets complexity requirements")


def root_hardening(resources: Sequence[Resource]) -> TestResult:
    accounts = _of_kind(resources, "iam_account")
    if not accounts:
        return TestResult(False, "Account-level root status unavailable")
    a = accounts[0].data
    problems = []
    if not a.get("root_mfa_enabled"):
        problems.append("root MFA disabled")
    if (a.get("root_access_keys") or 0) > 0:
        problems.append("root access keys present")
    if problems:
        return TestResult(False, f"Root account not hardened: {', '.join(problems)}")
    return TestResult(True, "Root account has MFA and no access keys")


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


def cloudtrail_logging(resources: Sequence[Resource]) -> TestResult:
    trails = _of_kind(resources, "cloudtrail")
    active = [t for t in trails if t.data.get("enabled") and t.data.get("multi_region")]
    if not active:
        return TestResult(False, "No active multi-region CloudTrail trail")
    return TestResult(True, f"{len(active)} multi-region CloudTrail trail(s) logging")


class AWSConnector:
    key = "aws"
    name = "Amazon Web Services"
    description = "IAM MFA & password policy, root hardening, S3 access/encryption, CloudTrail."
    credential_fields = ["access_key_id", "secret_access_key", "region"]

    tests = [
        ControlTest("aws.iam.mfa", ["CC6.1"], "IAM users have MFA enabled", iam_mfa),
        ControlTest(
            "aws.iam.password_policy",
            ["CC6.1"],
            "Strong IAM account password policy",
            iam_password_policy,
        ),
        ControlTest(
            "aws.iam.root_hardening",
            ["CC6.1"],
            "Root account hardened (MFA, no access keys)",
            root_hardening,
        ),
        ControlTest("aws.s3.public", ["CC6.6"], "No public S3 buckets", s3_public),
        ControlTest("aws.s3.encryption", ["CC6.7"], "S3 buckets encrypted", s3_encryption),
        ControlTest(
            "aws.cloudtrail.logging",
            ["CC7.2"],
            "Multi-region CloudTrail logging enabled",
            cloudtrail_logging,
        ),
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

        try:
            pp = iam.get_account_password_policy()["PasswordPolicy"]
            resources.append(
                Resource(
                    "iam_password_policy",
                    "account",
                    {
                        "minimum_length": pp.get("MinimumPasswordLength", 0),
                        "require_symbols": pp.get("RequireSymbols", False),
                        "require_numbers": pp.get("RequireNumbers", False),
                    },
                )
            )
        except Exception:
            pass  # NoSuchEntity when no policy is set -> the test reports it missing

        try:
            summary = iam.get_account_summary().get("SummaryMap", {})
            resources.append(
                Resource(
                    "iam_account",
                    "root",
                    {
                        "root_mfa_enabled": bool(summary.get("AccountMFAEnabled", 0)),
                        "root_access_keys": summary.get("AccountAccessKeysPresent", 0),
                    },
                )
            )
        except Exception:
            pass

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

        try:
            ct = session.client("cloudtrail")
            for trail in ct.describe_trails().get("trailList", []):
                name = trail.get("Name", "trail")
                status = ct.get_trail_status(Name=trail.get("TrailARN", name))
                resources.append(
                    Resource(
                        "cloudtrail",
                        name,
                        {
                            "enabled": bool(status.get("IsLogging", False)),
                            "multi_region": bool(trail.get("IsMultiRegionTrail", False)),
                        },
                    )
                )
        except Exception:
            pass

        return resources
