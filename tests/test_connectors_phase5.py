"""Phase 5B — new connector control-tests.

These are **pure functions over synthetic Resources**: no cloud accounts, no
network, no database. They are the bulk of the compliance logic and run fully
hermetically in CI. (Live ``collect()`` validation is a manual sandbox pass,
never a CI dependency.) One DB-gated test checks the expanded catalog seeds.
"""

import pytest
import yaml
from conftest import db_available
from refle_integrations.base import Resource
from refle_integrations.connectors.aws import (
    AWSConnector,
    cloudtrail_logging,
    iam_password_policy,
    root_hardening,
)
from refle_integrations.connectors.github import (
    GitHubConnector,
    secret_scanning,
    vulnerability_alerts,
)
from refle_integrations.connectors.okta import (
    OktaConnector,
    inactive_users,
    password_policy,
)

# --- AWS ---


def test_iam_password_policy():
    strong = [
        Resource(
            "iam_password_policy",
            "account",
            {"minimum_length": 16, "require_symbols": True, "require_numbers": True},
        )
    ]
    assert iam_password_policy(strong).passed is True
    weak = [
        Resource(
            "iam_password_policy",
            "account",
            {"minimum_length": 8, "require_symbols": False, "require_numbers": True},
        )
    ]
    assert iam_password_policy(weak).passed is False
    assert iam_password_policy([]).passed is False  # no policy configured


def test_root_hardening():
    good = [Resource("iam_account", "root", {"root_mfa_enabled": True, "root_access_keys": 0})]
    assert root_hardening(good).passed is True
    bad = [Resource("iam_account", "root", {"root_mfa_enabled": False, "root_access_keys": 1})]
    assert root_hardening(bad).passed is False
    assert root_hardening([]).passed is False


def test_cloudtrail_logging():
    on = [Resource("cloudtrail", "t", {"enabled": True, "multi_region": True})]
    assert cloudtrail_logging(on).passed is True
    single = [Resource("cloudtrail", "t", {"enabled": True, "multi_region": False})]
    assert cloudtrail_logging(single).passed is False
    assert cloudtrail_logging([]).passed is False


# --- GitHub ---


def test_secret_scanning():
    good = [Resource("github_repo", "r", {"secret_scanning": True})]
    assert secret_scanning(good).passed is True
    mixed = [
        Resource("github_repo", "ok", {"secret_scanning": True}),
        Resource("github_repo", "bad", {"secret_scanning": False}),
    ]
    assert secret_scanning(mixed).passed is False


def test_vulnerability_alerts():
    good = [Resource("github_repo", "r", {"vulnerability_alerts": True})]
    assert vulnerability_alerts(good).passed is True
    bad = [Resource("github_repo", "r", {"vulnerability_alerts": False})]
    assert vulnerability_alerts(bad).passed is False


# --- Okta ---


def test_okta_password_policy():
    strong = [Resource("okta_password_policy", "d", {"min_length": 14, "lockout_enabled": True})]
    assert password_policy(strong).passed is True
    short = [Resource("okta_password_policy", "d", {"min_length": 6, "lockout_enabled": True})]
    assert password_policy(short).passed is False
    assert password_policy([]).passed is False


def test_inactive_users():
    fresh = [Resource("okta_user", "a@x.com", {"status": "ACTIVE", "last_login_days": 10})]
    assert inactive_users(fresh).passed is True
    stale = [Resource("okta_user", "b@x.com", {"status": "ACTIVE", "last_login_days": 120})]
    assert inactive_users(stale).passed is False
    # A dormant but already-deprovisioned account is not a finding.
    gone = [Resource("okta_user", "c@x.com", {"status": "DEPROVISIONED", "last_login_days": 999})]
    assert inactive_users(gone).passed is True


# --- Mapping consistency (hermetic): every test maps to a catalog control ---


def test_every_control_test_maps_to_a_catalog_code():
    from refle_api.seed import _DEFAULT_CONTENT

    catalog = yaml.safe_load(_DEFAULT_CONTENT.read_text())
    codes = {c["code"] for c in catalog["controls"]}

    for connector in (AWSConnector(), GitHubConnector(), OktaConnector()):
        for test in connector.tests:
            for code in test.control_codes:
                assert code in codes, f"{test.key} maps to unknown control {code}"


# --- Catalog seed (DB-gated) ---


@pytest.mark.skipif(not db_available(), reason="requires Postgres on :5432")
async def test_seed_expands_catalog():
    from refle_api.seed import seed_soc2
    from refle_core.db import get_sessionmaker
    from refle_core.models import Control, Framework
    from sqlalchemy import select

    async with get_sessionmaker()() as session:
        await seed_soc2(session)
        fw = (
            await session.execute(select(Framework).where(Framework.key == "soc2"))
        ).scalar_one()
        codes = set(
            (
                await session.execute(select(Control.code).where(Control.framework_id == fw.id))
            )
            .scalars()
            .all()
        )

    assert {"CC7.1", "CC6.8", "CC9.2"} <= codes  # new controls landed
    assert len(codes) >= 25
