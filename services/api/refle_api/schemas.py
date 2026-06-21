"""Pydantic request/response models for the API."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field
from refle_core.models import (
    AccessDecision,
    AccessReviewStatus,
    ChecklistKind,
    ConnectionStatus,
    ControlStatus,
    EvidenceSource,
    InvitationStatus,
    NotificationLevel,
    PersonStatus,
    RemediationStatus,
    Role,
    TemplateType,
)
from refle_core.models.policy import PolicyVersionStatus

# --- Auth ---


class RegisterRequest(BaseModel):
    org_name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=200)
    full_name: str | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class AuthToken(BaseModel):
    access_token: str
    token_type: str = "bearer"
    organization_id: uuid.UUID
    role: Role


class OrgOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    slug: str


class MembershipOut(BaseModel):
    organization: OrgOut
    role: Role


class MeResponse(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str | None
    organization_id: uuid.UUID
    role: Role
    memberships: list[MembershipOut]


# --- Invitations ---


class InvitationCreate(BaseModel):
    email: EmailStr
    role: Role = Role.member


class InvitationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    email: str
    role: Role
    status: InvitationStatus
    token: str
    expires_at: datetime


class AcceptInviteRequest(BaseModel):
    token: str
    password: str | None = Field(default=None, min_length=8, max_length=200)
    full_name: str | None = None


# --- Controls / posture ---


class ControlOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    code: str
    title: str
    description: str | None
    category: str | None


class OrgControlOut(BaseModel):
    id: uuid.UUID
    control: ControlOut
    status: ControlStatus
    owner_id: uuid.UUID | None


class OrgControlUpdate(BaseModel):
    status: ControlStatus | None = None
    owner_id: uuid.UUID | None = None


class PostureSummary(BaseModel):
    total: int
    passing: int
    failing: int
    not_assessed: int
    percent_passing: float


class PostureSnapshotOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    passing: int
    failing: int
    not_assessed: int
    percent_ready: int
    created_at: datetime


# --- Reports / readiness ---


class ControlCoverageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    control_code: str
    title: str
    category: str | None
    status: ControlStatus
    owner_id: uuid.UUID | None
    evidence_count: int
    open_remediations: int
    last_tested_at: datetime | None
    last_test_passed: bool | None


class FrameworkProgressOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    framework_key: str
    name: str
    total: int
    passing: int
    failing: int
    not_assessed: int
    percent_ready: int


class ReadinessReport(BaseModel):
    framework: FrameworkProgressOut
    controls: list[ControlCoverageOut]


class GapOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    kind: str
    severity: str
    title: str
    recommendation: str
    control_code: str | None = None


# --- Evidence ---


class EvidenceOut(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    filename: str
    content_type: str | None
    size_bytes: int
    source: EvidenceSource
    uploaded_by_id: uuid.UUID | None
    control_codes: list[str]
    created_at: datetime


class DownloadUrl(BaseModel):
    url: str


# --- Policies ---


class PolicyTemplateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    description: str | None
    type: TemplateType
    organization_id: uuid.UUID | None
    created_at: datetime


class PolicyTemplateDetailOut(PolicyTemplateOut):
    body: str


class PolicyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    slug: str | None = None
    description: str | None = None
    body: str = Field(min_length=1)


class PolicyVersionCreate(BaseModel):
    body: str = Field(min_length=1)


class PolicyVersionUpdate(BaseModel):
    body: str = Field(min_length=1)


class PolicyVersionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    version: int
    body: str
    created_at: datetime
    status: PolicyVersionStatus


class PolicyOut(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    description: str | None
    latest_version: int | None
    accepted_count: int
    accepted_by_me: bool


class PolicyDetail(PolicyOut):
    versions: list[PolicyVersionOut]


class AcceptanceOut(BaseModel):
    user_id: uuid.UUID
    version: int
    accepted_at: datetime


# --- Integrations / connections ---


class ConnectorInfo(BaseModel):
    key: str
    name: str
    description: str
    credential_fields: list[str]


class ConnectionCreate(BaseModel):
    provider: str
    label: str = Field(min_length=1, max_length=120)
    credentials: dict[str, str] = Field(default_factory=dict)


class ConnectionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    provider: str
    label: str
    status: ConnectionStatus
    last_synced_at: datetime | None
    last_error: str | None
    monitoring_enabled: bool
    sync_interval_minutes: int | None
    created_at: datetime


class ConnectionUpdate(BaseModel):
    monitoring_enabled: bool | None = None
    sync_interval_minutes: int | None = Field(default=None, ge=1)


class SyncResult(BaseModel):
    ok: bool
    tests_run: int
    failures: int
    error: str | None = None


class TestResultOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    test_key: str
    control_code: str
    passed: bool
    detail: str | None
    created_at: datetime


class RemediationTaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    title: str
    control_code: str | None
    detail: str | None
    status: RemediationStatus
    created_at: datetime


# --- AI assistant (RAG) ---


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)


class DraftPolicyRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    instructions: str | None = None
    template_id: uuid.UUID | None = None
    evidence_id: uuid.UUID | None = None


class Citation(BaseModel):
    n: int
    source_type: str
    source_id: str
    title: str


class ChatResponse(BaseModel):
    answer: str
    citations: list[Citation]
    generated: bool  # False when the LLM is unavailable (retrieval-only fallback)
    model: str


class ReindexResult(BaseModel):
    indexed: int


class AIStatus(BaseModel):
    provider: str
    model: str
    agent_model: str
    sovereign: bool
    embedding_provider: str
    indexed_chunks: int


# --- Notifications ---


class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    type: str
    title: str
    body: str
    level: NotificationLevel
    read_at: datetime | None
    created_at: datetime


class NotificationSettingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    channels: str
    email_to: str | None
    slack_webhook_configured: bool


class NotificationSettingUpdate(BaseModel):
    channels: str | None = None
    email_to: str | None = None
    slack_webhook_url: str | None = None


# --- People & access reviews ---


class PersonCreate(BaseModel):
    full_name: str = Field(min_length=1, max_length=200)
    email: EmailStr
    title: str | None = None
    start_date: date | None = None
    manager_id: uuid.UUID | None = None


class PersonUpdate(BaseModel):
    full_name: str | None = None
    title: str | None = None
    status: PersonStatus | None = None
    end_date: date | None = None
    manager_id: uuid.UUID | None = None


class PersonOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    full_name: str
    email: str
    title: str | None
    status: PersonStatus
    start_date: date | None
    end_date: date | None
    manager_id: uuid.UUID | None
    user_id: uuid.UUID | None
    created_at: datetime


class ChecklistItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    person_id: uuid.UUID
    kind: ChecklistKind
    label: str
    done_at: datetime | None


class TrainingCreate(BaseModel):
    course: str = Field(min_length=1, max_length=200)
    completed_at: date | None = None
    expires_at: date | None = None


class TrainingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    person_id: uuid.UUID
    course: str
    completed_at: date | None
    expires_at: date | None


class AccessReviewItemInput(BaseModel):
    system: str = Field(min_length=1, max_length=120)
    person_id: uuid.UUID | None = None
    access_detail: str | None = None


class AccessReviewCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    due_at: datetime | None = None
    items: list[AccessReviewItemInput] = Field(default_factory=list)


class AccessReviewItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    person_id: uuid.UUID | None
    system: str
    access_detail: str | None
    decision: AccessDecision
    reviewed_at: datetime | None


class AccessReviewOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    status: AccessReviewStatus
    due_at: datetime | None
    completed_at: datetime | None
    created_at: datetime


class AccessReviewDetail(AccessReviewOut):
    items: list[AccessReviewItemOut]


class AccessDecisionInput(BaseModel):
    decision: AccessDecision
