"""Importing this package registers every model on ``Base.metadata``.

Alembic's ``env.py`` imports it so autogenerate sees the full schema.
"""

from refle_core.models.base import Base
from refle_core.models.compliance import (
    Control,
    ControlStatus,
    Framework,
    OrgControl,
)
from refle_core.models.evidence import Evidence, EvidenceControl, EvidenceSource
from refle_core.models.integration import (
    Connection,
    ConnectionStatus,
    ControlTestResult,
    RemediationStatus,
    RemediationTask,
)
from refle_core.models.invitation import Invitation, InvitationStatus
from refle_core.models.organization import Organization
from refle_core.models.policy import Policy, PolicyAcceptance, PolicyVersion
from refle_core.models.user import Membership, Role, User

__all__ = [
    "Base",
    "Organization",
    "User",
    "Membership",
    "Role",
    "Invitation",
    "InvitationStatus",
    "Framework",
    "Control",
    "OrgControl",
    "ControlStatus",
    "Evidence",
    "EvidenceControl",
    "EvidenceSource",
    "Policy",
    "PolicyVersion",
    "PolicyAcceptance",
    "Connection",
    "ConnectionStatus",
    "ControlTestResult",
    "RemediationTask",
    "RemediationStatus",
]
