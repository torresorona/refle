"""Pydantic request/response models for the API."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field
from refle_core.models import (
    ConnectionStatus,
    ControlStatus,
    EvidenceSource,
    InvitationStatus,
    RemediationStatus,
    Role,
)

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


class PolicyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    slug: str | None = None
    description: str | None = None
    body: str = Field(min_length=1)


class PolicyVersionCreate(BaseModel):
    body: str = Field(min_length=1)


class PolicyVersionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    version: int
    body: str
    created_at: datetime


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
    created_at: datetime


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
