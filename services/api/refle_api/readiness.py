"""Audit-readiness aggregation: per-control coverage, framework progress, gaps.

Reads existing Phase 1–4 data (controls, evidence, tests, remediation, policies);
adds no new tables. Used by the reports API and the audit-package export.
"""

from __future__ import annotations

import csv
import io
import json
import uuid
import zipfile
from dataclasses import dataclass
from datetime import UTC, date, datetime

from refle_core.models import (
    ChecklistItem,
    ChecklistKind,
    Control,
    ControlStatus,
    ControlTestResult,
    Evidence,
    EvidenceControl,
    Framework,
    Organization,
    OrgControl,
    Person,
    PersonStatus,
    Policy,
    PolicyAcceptance,
    PolicyVersion,
    RemediationStatus,
    RemediationTask,
    TrainingRecord,
)
from refle_core.models.policy import PolicyVersionStatus
from refle_core.posture import posture_counts
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

SOC2_FRAMEWORK_KEY = "soc2"


@dataclass
class ControlCoverage:
    control_code: str
    title: str
    category: str | None
    status: str
    owner_id: uuid.UUID | None
    evidence_count: int
    open_remediations: int
    last_tested_at: datetime | None
    last_test_passed: bool | None
    in_scope: bool


@dataclass
class FrameworkProgress:
    framework_key: str
    name: str
    total: int
    passing: int
    failing: int
    not_assessed: int
    percent_ready: int


@dataclass
class Gap:
    kind: str
    severity: str  # "high" | "medium" | "low"
    title: str
    recommendation: str
    control_code: str | None = None


async def control_coverage(session: AsyncSession, org_id: uuid.UUID) -> list[ControlCoverage]:
    rows = (
        await session.execute(
            select(OrgControl, Control)
            .join(Control, OrgControl.control_id == Control.id)
            .where(OrgControl.organization_id == org_id)
            .order_by(Control.code)
        )
    ).all()

    ev_rows = (
        await session.execute(
            select(EvidenceControl.org_control_id, func.count())
            .join(Evidence, EvidenceControl.evidence_id == Evidence.id)
            .where(Evidence.organization_id == org_id)
            .group_by(EvidenceControl.org_control_id)
        )
    ).all()
    ev_by_oc = {oc_id: n for oc_id, n in ev_rows}

    rem_rows = (
        await session.execute(
            select(RemediationTask.control_code, func.count())
            .where(
                RemediationTask.organization_id == org_id,
                RemediationTask.status == RemediationStatus.open,
            )
            .group_by(RemediationTask.control_code)
        )
    ).all()
    rem_by_code = {code: n for code, n in rem_rows if code}

    # Latest test result per control code (rows come newest-first).
    test_rows = (
        await session.execute(
            select(
                ControlTestResult.control_code,
                ControlTestResult.passed,
                ControlTestResult.created_at,
            )
            .where(ControlTestResult.organization_id == org_id)
            .order_by(ControlTestResult.created_at.desc())
        )
    ).all()
    last_test: dict[str, tuple[bool, datetime]] = {}
    for code, passed, created in test_rows:
        last_test.setdefault(code, (passed, created))

    out = []
    for oc, c in rows:
        passed, tested_at = last_test.get(c.code, (None, None))
        out.append(
            ControlCoverage(
                control_code=c.code,
                title=c.title,
                category=c.category,
                status=oc.status.value,
                owner_id=oc.owner_id,
                evidence_count=ev_by_oc.get(oc.id, 0),
                open_remediations=rem_by_code.get(c.code, 0),
                last_tested_at=tested_at,
                last_test_passed=passed,
                in_scope=oc.in_scope,
            )
        )
    return out


async def framework_progress(session: AsyncSession, org_id: uuid.UUID) -> FrameworkProgress:
    pc = await posture_counts(session, org_id)
    fw = (
        await session.execute(select(Framework).where(Framework.key == SOC2_FRAMEWORK_KEY))
    ).scalar_one_or_none()
    return FrameworkProgress(
        framework_key=fw.key if fw else SOC2_FRAMEWORK_KEY,
        name=fw.name if fw else "SOC 2",
        total=pc.total,
        passing=pc.passing,
        failing=pc.failing,
        not_assessed=pc.not_assessed,
        percent_ready=pc.percent_ready,
    )


async def compute_gaps(session: AsyncSession, org_id: uuid.UUID) -> list[Gap]:
    gaps: list[Gap] = []
    for c in await control_coverage(session, org_id):
        if not c.in_scope:
            continue  # out-of-scope controls aren't gaps
        if c.status == ControlStatus.failing.value:
            gaps.append(
                Gap(
                    "control_failing",
                    "high",
                    f"{c.control_code} is failing",
                    "Investigate the failing automated test and remediate.",
                    c.control_code,
                )
            )
        elif c.status == ControlStatus.not_assessed.value:
            gaps.append(
                Gap(
                    "control_not_assessed",
                    "medium",
                    f"{c.control_code} has not been assessed",
                    "Connect an integration or attach evidence to assess this control.",
                    c.control_code,
                )
            )
        if c.evidence_count == 0:
            gaps.append(
                Gap(
                    "no_evidence",
                    "medium",
                    f"{c.control_code} has no evidence",
                    "Attach at least one piece of evidence for this control.",
                    c.control_code,
                )
            )
        if c.owner_id is None:
            gaps.append(
                Gap(
                    "no_owner",
                    "low",
                    f"{c.control_code} has no owner",
                    "Assign an owner accountable for this control.",
                    c.control_code,
                )
            )

    policies = (
        (await session.execute(select(Policy).where(Policy.organization_id == org_id)))
        .scalars()
        .all()
    )
    for p in policies:
        latest_pub = (
            (
                await session.execute(
                    select(PolicyVersion)
                    .where(
                        PolicyVersion.policy_id == p.id,
                        PolicyVersion.status == PolicyVersionStatus.published,
                    )
                    .order_by(PolicyVersion.version.desc())
                )
            )
            .scalars()
            .first()
        )
        if latest_pub is None:
            gaps.append(
                Gap(
                    "policy_unpublished",
                    "medium",
                    f"Policy '{p.name}' has no published version",
                    "Publish the policy so employees can review and accept it.",
                )
            )
            continue
        accepted = (
            await session.execute(
                select(func.count(PolicyAcceptance.id)).where(
                    PolicyAcceptance.policy_version_id == latest_pub.id
                )
            )
        ).scalar_one()
        if accepted == 0:
            gaps.append(
                Gap(
                    "policy_unaccepted",
                    "low",
                    f"Policy '{p.name}' has no acceptances",
                    "Have employees review and accept the published policy.",
                )
            )

    # People: expired training (CC1) and incomplete offboarding (CC6).
    today = date.today()
    expired = (
        (
            await session.execute(
                select(TrainingRecord, Person)
                .join(Person, TrainingRecord.person_id == Person.id)
                .where(
                    TrainingRecord.organization_id == org_id,
                    TrainingRecord.expires_at.is_not(None),
                    TrainingRecord.expires_at < today,
                )
            )
        )
        .all()
    )
    for record, person in expired:
        gaps.append(
            Gap(
                "training_expired",
                "medium",
                f"Training '{record.course}' expired for {person.full_name}",
                "Reassign and complete the required security training.",
            )
        )

    incomplete_offboarding = (
        (
            await session.execute(
                select(Person.full_name, func.count(ChecklistItem.id))
                .join(ChecklistItem, ChecklistItem.person_id == Person.id)
                .where(
                    Person.organization_id == org_id,
                    Person.status == PersonStatus.terminated,
                    ChecklistItem.kind == ChecklistKind.offboarding,
                    ChecklistItem.done_at.is_(None),
                )
                .group_by(Person.id, Person.full_name)
            )
        )
        .all()
    )
    for name, pending in incomplete_offboarding:
        gaps.append(
            Gap(
                "offboarding_incomplete",
                "high",
                f"Offboarding incomplete for {name} ({pending} step(s) pending)",
                "Complete all offboarding steps to fully revoke access.",
            )
        )

    return gaps


def _readiness_summary_md(fp: FrameworkProgress, gaps: list[Gap]) -> str:
    by_sev = {"high": 0, "medium": 0, "low": 0}
    for g in gaps:
        by_sev[g.severity] = by_sev.get(g.severity, 0) + 1
    lines = [
        f"# {fp.name} — Readiness Summary",
        "",
        f"- Controls: **{fp.total}** (passing {fp.passing}, failing {fp.failing}, "
        f"not assessed {fp.not_assessed})",
        f"- Readiness: **{fp.percent_ready}%**",
        f"- Open gaps: {len(gaps)} (high {by_sev['high']}, medium {by_sev['medium']}, "
        f"low {by_sev['low']})",
        "",
        "## Top gaps",
    ]
    for g in gaps[:25]:
        scope = f" ({g.control_code})" if g.control_code else ""
        lines.append(f"- [{g.severity}] {g.title}{scope} — {g.recommendation}")
    if not gaps:
        lines.append("- None. All assessed controls are passing with evidence and owners.")
    return "\n".join(lines) + "\n"


def _controls_md(coverage: list[ControlCoverage]) -> str:
    lines = [
        "# Control Coverage",
        "",
        "| Code | Title | Status | Owner | Evidence | Open remediations | Last tested |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for c in coverage:
        owner = str(c.owner_id) if c.owner_id else "—"
        tested = c.last_tested_at.date().isoformat() if c.last_tested_at else "—"
        lines.append(
            f"| {c.control_code} | {c.title} | {c.status} | {owner} | "
            f"{c.evidence_count} | {c.open_remediations} | {tested} |"
        )
    return "\n".join(lines) + "\n"


async def _policies_md(session: AsyncSession, org_id: uuid.UUID) -> str:
    policies = (
        (await session.execute(select(Policy).where(Policy.organization_id == org_id)))
        .scalars()
        .all()
    )
    lines = ["# Policies", ""]
    if not policies:
        lines.append("_No policies._")
        return "\n".join(lines) + "\n"
    for p in policies:
        latest_pub = (
            (
                await session.execute(
                    select(PolicyVersion)
                    .where(
                        PolicyVersion.policy_id == p.id,
                        PolicyVersion.status == PolicyVersionStatus.published,
                    )
                    .order_by(PolicyVersion.version.desc())
                )
            )
            .scalars()
            .first()
        )
        lines.append(f"## {p.name}")
        if latest_pub is None:
            lines.append("_No published version._\n")
            continue
        accepted = (
            await session.execute(
                select(func.count(PolicyAcceptance.id)).where(
                    PolicyAcceptance.policy_version_id == latest_pub.id
                )
            )
        ).scalar_one()
        lines.append(f"_Version {latest_pub.version} · {accepted} acceptance(s)_\n")
        lines.append(latest_pub.body)
        lines.append("")
    return "\n".join(lines) + "\n"


async def _evidence_index_csv(session: AsyncSession, org_id: uuid.UUID) -> str:
    from refle_api import storage

    evidence = (
        (
            await session.execute(
                select(Evidence)
                .where(Evidence.organization_id == org_id)
                .order_by(Evidence.name)
            )
        )
        .scalars()
        .all()
    )
    code_rows = (
        await session.execute(
            select(EvidenceControl.evidence_id, Control.code)
            .join(OrgControl, EvidenceControl.org_control_id == OrgControl.id)
            .join(Control, OrgControl.control_id == Control.id)
            .where(OrgControl.organization_id == org_id)
        )
    ).all()
    codes_by_ev: dict[uuid.UUID, list[str]] = {}
    for ev_id, code in code_rows:
        codes_by_ev.setdefault(ev_id, []).append(code)

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["name", "filename", "control_codes", "sha256", "download_url"])
    for ev in evidence:
        try:
            url = storage.presigned_get(ev.object_key)
        except Exception:
            url = ""
        writer.writerow(
            [
                ev.name,
                ev.filename,
                ";".join(sorted(codes_by_ev.get(ev.id, []))),
                ev.content_sha256 or "",
                url,
            ]
        )
    return buf.getvalue()


async def build_audit_package(
    session: AsyncSession, organization: Organization, edition: str
) -> bytes:
    """Build an in-memory ZIP auditors can consume. Works with AI off."""
    org_id = organization.id
    fp = await framework_progress(session, org_id)
    coverage = await control_coverage(session, org_id)
    gaps = await compute_gaps(session, org_id)
    summary_md = _readiness_summary_md(fp, gaps)

    # Optional AI narrative (records an AiRun); falls back to the templated summary.
    narrative = "# System Security Plan (Narrative)\n\n" + summary_md
    try:
        from refle_core.ai_runs import record_agent_run
        from refle_extensions.registry import agent_registry

        agent = agent_registry.get("ssp-narrative")
        result, _ = await record_agent_run(
            session,
            organization_id=org_id,
            agent=agent,
            context={"summary": summary_md},
            params={},
            input_record={"kind": "audit-package"},
        )
        narrative = result.output
        await session.commit()
    except Exception:  # noqa: BLE001 - narrative is optional; keep the templated one
        await session.rollback()

    manifest = {
        "organization": organization.name,
        "framework": {"key": fp.framework_key, "name": fp.name},
        "generated_at": datetime.now(UTC).isoformat(),
        "edition": edition,
        "percent_ready": fp.percent_ready,
        "counts": {
            "total": fp.total,
            "passing": fp.passing,
            "failing": fp.failing,
            "not_assessed": fp.not_assessed,
        },
        "open_gaps": len(gaps),
    }
    controls_json = [
        {
            "control_code": c.control_code,
            "title": c.title,
            "category": c.category,
            "status": c.status,
            "owner_id": str(c.owner_id) if c.owner_id else None,
            "evidence_count": c.evidence_count,
            "open_remediations": c.open_remediations,
            "last_tested_at": c.last_tested_at.isoformat() if c.last_tested_at else None,
            "last_test_passed": c.last_test_passed,
        }
        for c in coverage
    ]

    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.json", json.dumps(manifest, indent=2))
        zf.writestr("readiness_summary.md", summary_md)
        zf.writestr("controls.json", json.dumps(controls_json, indent=2))
        zf.writestr("controls.md", _controls_md(coverage))
        zf.writestr("policies.md", await _policies_md(session, org_id))
        zf.writestr("evidence_index.csv", await _evidence_index_csv(session, org_id))
        zf.writestr("ssp_narrative.md", narrative)
    return out.getvalue()
