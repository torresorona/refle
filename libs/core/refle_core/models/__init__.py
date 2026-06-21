"""Importing this package registers every model on ``Base.metadata``.

Alembic's ``env.py`` imports it so autogenerate sees the full schema.
"""

from refle_core.models.ai_run import AiRun, AiRunStatus
from refle_core.models.audit import AuditLog
from refle_core.models.base import Base
from refle_core.models.compliance import (
    Control,
    ControlStatus,
    Framework,
    OrgControl,
)
from refle_core.models.embedding import Embedding
from refle_core.models.evidence import Evidence, EvidenceControl, EvidenceSource
from refle_core.models.integration import (
    Connection,
    ConnectionStatus,
    ControlTestResult,
    PostureSnapshot,
    RemediationStatus,
    RemediationTask,
)
from refle_core.models.invitation import Invitation, InvitationStatus
from refle_core.models.notification import Notification, NotificationLevel, NotificationSetting
from refle_core.models.organization import Organization
from refle_core.models.people import (
    AccessDecision,
    AccessReview,
    AccessReviewItem,
    AccessReviewStatus,
    ChecklistItem,
    ChecklistKind,
    Person,
    PersonStatus,
    TrainingRecord,
)
from refle_core.models.policy import (
    Policy,
    PolicyAcceptance,
    PolicyTemplate,
    PolicyVersion,
    PolicyVersionStatus,
    TemplateType,
)
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
    "PolicyTemplate",
    "PolicyVersionStatus",
    "TemplateType",
    "Connection",
    "ConnectionStatus",
    "ControlTestResult",
    "PostureSnapshot",
    "RemediationTask",
    "RemediationStatus",
    "Embedding",
    "AiRun",
    "AiRunStatus",
    "AuditLog",
    "Notification",
    "NotificationLevel",
    "NotificationSetting",
    "PolicyVersionStatus",
    "Person",
    "PersonStatus",
    "ChecklistItem",
    "ChecklistKind",
    "TrainingRecord",
    "AccessReview",
    "AccessReviewStatus",
    "AccessReviewItem",
    "AccessDecision",
]
