"""Okta connector — MFA enrolment and user lifecycle via the Okta API."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from refle_integrations.base import ControlTest, Resource, TestResult

_MIN_PASSWORD_LENGTH = 12
_MAX_IDLE_DAYS = 90


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


def password_policy(resources: Sequence[Resource]) -> TestResult:
    policies = _of_kind(resources, "okta_password_policy")
    if not policies:
        return TestResult(False, "No Okta password policy configured")
    p = policies[0].data
    problems = []
    if (p.get("min_length") or 0) < _MIN_PASSWORD_LENGTH:
        problems.append(f"min length < {_MIN_PASSWORD_LENGTH}")
    if not p.get("lockout_enabled"):
        problems.append("account lockout not enabled")
    if problems:
        return TestResult(False, f"Weak password policy: {', '.join(problems)}")
    return TestResult(True, "Okta password policy meets requirements")


def inactive_users(resources: Sequence[Resource]) -> TestResult:
    stale = []
    for u in _of_kind(resources, "okta_user"):
        if u.data.get("status") != "ACTIVE":
            continue
        if (u.data.get("last_login_days") or 0) > _MAX_IDLE_DAYS:
            stale.append(u.external_id)
    if stale:
        return TestResult(False, f"Active users idle > {_MAX_IDLE_DAYS}d: {', '.join(stale)}")
    return TestResult(True, "No stale active accounts")


class OktaConnector:
    key = "okta"
    name = "Okta"
    description = "MFA enrolment, password policy, lifecycle hygiene, and dormant accounts."
    credential_fields = ["domain", "api_token"]

    tests = [
        ControlTest("okta.mfa", ["CC6.1"], "Active users enrolled in MFA", mfa_enrolled),
        ControlTest(
            "okta.password_policy", ["CC6.1"], "Strong Okta password policy", password_policy
        ),
        ControlTest("okta.lifecycle", ["CC6.2"], "User provisioning is complete", lifecycle),
        ControlTest(
            "okta.inactive_users", ["CC6.2"], "No dormant active accounts", inactive_users
        ),
    ]

    def authenticate(self, credentials: dict[str, Any]) -> Any:
        return {"domain": credentials.get("domain"), "api_token": credentials.get("api_token")}

    def collect(self, session: Any) -> list[Resource]:  # pragma: no cover - needs Okta
        from datetime import UTC, datetime

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
                last_login_days = None
                if user.get("lastLogin"):
                    try:
                        last = datetime.fromisoformat(user["lastLogin"].replace("Z", "+00:00"))
                        last_login_days = (datetime.now(UTC) - last).days
                    except Exception:
                        last_login_days = None
                resources.append(
                    Resource(
                        "okta_user",
                        user.get("profile", {}).get("email", uid),
                        {
                            "status": status,
                            "mfa_enrolled": enrolled,
                            "last_login_days": last_login_days,
                        },
                    )
                )

            try:
                policies = client.get(
                    "/api/v1/policies", params={"type": "PASSWORD"}
                ).json()
                if policies:
                    settings = (policies[0].get("settings") or {}).get("password") or {}
                    complexity = settings.get("complexity") or {}
                    lockout = settings.get("lockout") or {}
                    resources.append(
                        Resource(
                            "okta_password_policy",
                            policies[0].get("id", "default"),
                            {
                                "min_length": complexity.get("minLength", 0),
                                "lockout_enabled": (lockout.get("maxAttempts") or 0) > 0,
                            },
                        )
                    )
            except Exception:
                pass

        return resources
