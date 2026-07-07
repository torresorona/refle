"""Public setup and deployment configuration status."""

from __future__ import annotations

from fastapi import APIRouter
from refle_ai_core.config import get_ai_settings
from refle_core.config import get_settings
from refle_core.models import Organization
from sqlalchemy import select

from refle_api.deps import SessionDep
from refle_api.schemas import SetupConfigurationItem, SetupStatus

router = APIRouter(prefix="/setup", tags=["setup"])


def _item(
    key: str,
    label: str,
    configured: bool,
    *,
    required: bool = False,
    detail: str | None = None,
) -> SetupConfigurationItem:
    return SetupConfigurationItem(
        key=key,
        label=label,
        configured=configured,
        required=required,
        detail=detail,
    )


def _ai_configured() -> tuple[bool, str]:
    settings = get_ai_settings()
    if settings.provider == "local":
        return True, f"Local provider using {settings.local_model}"
    if settings.provider == "gemini":
        return bool(settings.gemini_api_key), "Gemini provider"
    if settings.provider == "openai":
        return bool(settings.openai_api_key), "OpenAI provider"
    return False, f"Unknown provider: {settings.provider}"


@router.get("/status", response_model=SetupStatus)
async def setup_status(session: SessionDep) -> SetupStatus:
    settings = get_settings()
    org = (
        (
            await session.execute(
                select(Organization).order_by(Organization.created_at).limit(1)
            )
        )
        .scalars()
        .first()
    )
    ai_configured, ai_detail = _ai_configured()
    email_configured = bool(settings.resend_api_key) or bool(
        settings.smtp_host and settings.smtp_from
    )
    storage_configured = all(
        [
            settings.s3_endpoint_url,
            settings.s3_access_key,
            settings.s3_secret_key,
            settings.s3_bucket,
        ]
    )
    default_secret = "dev-only-insecure-secret-change-me-in-production"

    return SetupStatus(
        deployment_mode=settings.deployment_mode,
        edition=settings.edition,
        organization_configured=org is not None,
        organization_name=org.name if org else None,
        configuration=[
            _item(
                "deployment_mode",
                "Deployment mode",
                settings.deployment_mode == "self_hosted_core",
                required=True,
                detail=settings.deployment_mode,
            ),
            _item(
                "secret_key",
                "Application secret",
                bool(settings.secret_key and settings.secret_key != default_secret),
                required=True,
                detail="Set REFLE_SECRET_KEY",
            ),
            _item(
                "database",
                "Database",
                bool(settings.database_url),
                required=True,
                detail="Set REFLE_DATABASE_URL",
            ),
            _item(
                "redis",
                "Redis",
                bool(settings.redis_url),
                detail="Set REFLE_REDIS_URL",
            ),
            _item(
                "object_storage",
                "Object storage",
                storage_configured,
                required=True,
                detail="Set REFLE_S3_* values",
            ),
            _item(
                "email",
                "Email delivery",
                email_configured,
                detail="Set SMTP values or RESEND_API_KEY",
            ),
            _item(
                "ai_provider",
                "AI provider",
                ai_configured,
                detail=ai_detail,
            ),
            _item(
                "license",
                "License key",
                bool(settings.license_key),
                detail="Optional for Enterprise features",
            ),
        ],
    )
