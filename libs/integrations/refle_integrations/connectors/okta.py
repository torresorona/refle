"""Okta connector — MFA enrolment and user lifecycle via the Okta API."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from refle_integrations.base import ControlTest, Resource, TestResult


def _of_kind(resources: Sequence[Resource], kind: str) -> list[Resource]:
    return [r for r in resources if r.kind == kind]


def mfa_enrolled(resources: Sequence[Resource]) -> TestResult:
    users = [u for u in _of_kind(resources, "okta_user") if u.data.get("status") == "ACTIVE"]
    bad = [u.external_id for u in users if not u.data.get("mfa_enrolled")]
    if bad:
        return TestResult(False, f"Active users without MFA: {', '.join(bad)}")
    return TestResult(True, f"All {len(users)} active users enrolled in MFA")


def lifecycle(resources: Sequence[Resource]) -> TestResult:
    # Onboarding/offboarding should be complete: no accounts stuck mid-provisioning.
    stuck = [
        u.external_id
        for u in _of_kind(resources, "okta_user")
        if u.data.get("status") in {"STAGED", "PROVISIONED"}
    ]
    if stuck:
        return TestResult(False, f"Accounts stuck in provisioning: {', '.join(stuck)}")
    return TestResult(True, "No accounts stuck in provisioning")


class OktaConnector:
    key = "okta"
    name = "Okta"
    description = "MFA enrolment for active users and user-lifecycle hygiene."
    credential_fields = ["domain", "api_token"]

    tests = [
        ControlTest("okta.mfa", ["CC6.1"], "Active users enrolled in MFA", mfa_enrolled),
        ControlTest("okta.lifecycle", ["CC6.2"], "User provisioning is complete", lifecycle),
    ]

    def authenticate(self, credentials: dict[str, Any]) -> Any:
        return {"domain": credentials.get("domain"), "api_token": credentials.get("api_token")}

    def collect(self, session: Any) -> list[Resource]:  # pragma: no cover - needs Okta
        import httpx

        base = f"https://{session['domain']}"
        headers = {"Authorization": f"SSWS {session['api_token']}", "Accept": "application/json"}
        resources: list[Resource] = []
        with httpx.Client(base_url=base, headers=headers, timeout=30) as client:
            users = client.get("/api/v1/users", params={"limit": 200}).json()
            for user in users:
                uid = user["id"]
                status = user.get("status", "ACTIVE")
                factors = client.get(f"/api/v1/users/{uid}/factors").json()
                enrolled = any(f.get("status") == "ACTIVE" for f in factors)
                resources.append(
                    Resource(
                        "okta_user",
                        user.get("profile", {}).get("email", uid),
                        {"status": status, "mfa_enrolled": enrolled},
                    )
                )
        return resources
