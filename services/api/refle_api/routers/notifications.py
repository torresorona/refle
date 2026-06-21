from fastapi import APIRouter
from refle_core.crypto import encrypt
from refle_core.models import Notification, NotificationSetting
from sqlalchemy import select

from refle_api.deps import AuthDep, OwnerOrAdmin, SessionDep
from refle_api.schemas import (
    NotificationOut,
    NotificationSettingOut,
    NotificationSettingUpdate,
)

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=list[NotificationOut])
async def list_notifications(ctx: AuthDep, session: SessionDep) -> list[NotificationOut]:
    rows = (
        (
            await session.execute(
                select(Notification)
                .where(Notification.organization_id == ctx.organization.id)
                .order_by(Notification.created_at.desc())
                .limit(50)
            )
        )
        .scalars()
        .all()
    )
    return [NotificationOut.model_validate(r) for r in rows]


@router.get("/settings", response_model=NotificationSettingOut)
async def get_settings(ctx: AuthDep, session: SessionDep) -> NotificationSettingOut:
    setting = (
        await session.execute(
            select(NotificationSetting).where(
                NotificationSetting.organization_id == ctx.organization.id
            )
        )
    ).scalar_one_or_none()

    if not setting:
        setting = NotificationSetting(organization_id=ctx.organization.id, channels="")
        session.add(setting)
        await session.commit()
        await session.refresh(setting)

    return NotificationSettingOut(
        id=setting.id,
        channels=setting.channels,
        email_to=setting.email_to,
        slack_webhook_configured=bool(setting.slack_webhook_url),
    )


@router.put("/settings", response_model=NotificationSettingOut)
async def update_settings(
    body: NotificationSettingUpdate, ctx: OwnerOrAdmin, session: SessionDep
) -> NotificationSettingOut:
    setting = (
        await session.execute(
            select(NotificationSetting).where(
                NotificationSetting.organization_id == ctx.organization.id
            )
        )
    ).scalar_one_or_none()

    if not setting:
        setting = NotificationSetting(organization_id=ctx.organization.id, channels="")
        session.add(setting)

    if body.channels is not None:
        setting.channels = body.channels
    if body.email_to is not None:
        setting.email_to = body.email_to
    if body.slack_webhook_url is not None:
        setting.slack_webhook_url = encrypt(body.slack_webhook_url)

    await session.commit()
    await session.refresh(setting)

    return NotificationSettingOut(
        id=setting.id,
        channels=setting.channels,
        email_to=setting.email_to,
        slack_webhook_configured=bool(setting.slack_webhook_url),
    )
