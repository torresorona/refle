"""GitHub connector — org 2FA and repo branch-protection via the REST API."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from refle_integrations.base import ControlTest, Resource, TestResult

_API = "https://api.github.com"


def _of_kind(resources: Sequence[Resource], kind: str) -> list[Resource]:
    return [r for r in resources if r.kind == kind]


def org_2fa(resources: Sequence[Resource]) -> TestResult:
    orgs = _of_kind(resources, "github_org")
    bad = [o.external_id for o in orgs if not o.data.get("two_factor_required")]
    if bad:
        return TestResult(False, f"Orgs without 2FA requirement: {', '.join(bad)}")
    return TestResult(True, "Org requires two-factor authentication")


def branch_protection(resources: Sequence[Resource]) -> TestResult:
    repos = _of_kind(resources, "github_repo")
    bad = [r.external_id for r in repos if not r.data.get("branch_protection")]
    if bad:
        return TestResult(False, f"Repos without default-branch protection: {', '.join(bad)}")
    return TestResult(True, f"All {len(repos)} repos protect their default branch")


class GitHubConnector:
    key = "github"
    name = "GitHub"
    description = "Org 2FA enforcement and default-branch protection."
    credential_fields = ["token", "org"]

    tests = [
        ControlTest("github.org.2fa", ["CC6.1"], "Org enforces 2FA", org_2fa),
        ControlTest(
            "github.repo.protection", ["CC8.1"], "Branch protection enabled", branch_protection
        ),
    ]

    def authenticate(self, credentials: dict[str, Any]) -> Any:
        return {"token": credentials.get("token"), "org": credentials.get("org")}

    def collect(self, session: Any) -> list[Resource]:  # pragma: no cover - needs GitHub
        import httpx

        org = session["org"]
        headers = {
            "Authorization": f"Bearer {session['token']}",
            "Accept": "application/vnd.github+json",
        }
        resources: list[Resource] = []
        with httpx.Client(base_url=_API, headers=headers, timeout=30) as client:
            org_data = client.get(f"/orgs/{org}").json()
            resources.append(
                Resource(
                    "github_org",
                    org,
                    {"two_factor_required": bool(org_data.get("two_factor_requirement_enabled"))},
                )
            )
            repos = client.get(f"/orgs/{org}/repos", params={"per_page": 100}).json()
            for repo in repos:
                name = repo["name"]
                default_branch = repo.get("default_branch", "main")
                protected = (
                    client.get(
                        f"/repos/{org}/{name}/branches/{default_branch}/protection"
                    ).status_code
                    == 200
                )
                resources.append(Resource("github_repo", name, {"branch_protection": protected}))
        return resources
