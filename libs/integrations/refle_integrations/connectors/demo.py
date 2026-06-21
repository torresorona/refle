"""Demo connector — synthetic data so the full pipeline runs without real credentials."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from refle_integrations.base import ControlTest, Resource, TestResult


def _of_kind(resources: Sequence[Resource], kind: str) -> list[Resource]:
    return [r for r in resources if r.kind == kind]


def _mfa(resources: Sequence[Resource]) -> TestResult:
    users = _of_kind(resources, "iam_user")
    bad = [u.external_id for u in users if not u.data.get("mfa_enabled")]
    if bad:
        return TestResult(False, f"Users without MFA: {', '.join(bad)}")
    return TestResult(True, f"All {len(users)} users have MFA enabled")


def _bucket_encryption(resources: Sequence[Resource]) -> TestResult:
    buckets = _of_kind(resources, "bucket")
    bad = [b.external_id for b in buckets if not b.data.get("encrypted")]
    if bad:
        return TestResult(False, f"Unencrypted buckets: {', '.join(bad)}")
    return TestResult(True, f"All {len(buckets)} buckets encrypted")


def _bucket_public(resources: Sequence[Resource]) -> TestResult:
    public = [b.external_id for b in _of_kind(resources, "bucket") if b.data.get("public")]
    if public:
        return TestResult(False, f"Publicly accessible buckets: {', '.join(public)}")
    return TestResult(True, "No publicly accessible buckets")


def _branch_protection(resources: Sequence[Resource]) -> TestResult:
    repos = _of_kind(resources, "repo")
    bad = [r.external_id for r in repos if not r.data.get("branch_protection")]
    if bad:
        return TestResult(False, f"Repos without branch protection: {', '.join(bad)}")
    return TestResult(True, f"All {len(repos)} repos enforce branch protection")


class DemoConnector:
    key = "demo"
    name = "Demo (synthetic data)"
    description = "Synthetic resources to exercise the pipeline without real credentials."
    credential_fields: list[str] = []

    tests = [
        ControlTest("demo.iam.mfa", ["CC6.1"], "All users have MFA enabled", _mfa),
        ControlTest(
            "demo.s3.encryption", ["CC6.7"], "Buckets encrypted at rest", _bucket_encryption
        ),
        ControlTest("demo.s3.public", ["CC6.6"], "No public buckets", _bucket_public),
        ControlTest(
            "demo.repo.protection", ["CC8.1"], "Branch protection enforced", _branch_protection
        ),
    ]

    def authenticate(self, credentials: dict[str, Any]) -> Any:
        return {}

    def collect(self, session: Any) -> list[Resource]:
        return [
            Resource("iam_user", "alice", {"mfa_enabled": True}),
            Resource("iam_user", "bob", {"mfa_enabled": False}),  # triggers CC6.1 failure
            Resource("bucket", "app-logs", {"public": False, "encrypted": True}),
            Resource("repo", "refle", {"branch_protection": True}),
        ]
