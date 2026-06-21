from email.message import EmailMessage

import aiosmtplib
import httpx
from refle_core.config import get_settings
from refle_core.crypto import decrypt
from refle_core.models import Notification, NotificationSetting
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


async def dispatch_notifications(session: AsyncSession, notifications: list[Notification]) -> None:
    if not notifications:
        return

    org_id = notifications[0].organization_id
    settings = (
        await session.execute(
            select(NotificationSetting).where(NotificationSetting.organization_id == org_id)
        )
    ).scalar_one_or_none()

    if not settings:
        return

    channels = [c.strip() for c in settings.channels.split(",") if c.strip()]
    app_settings = get_settings()

    async with httpx.AsyncClient() as client:
        for notification in notifications:
            if "slack" in channels and settings.slack_webhook_url:
                webhook_url = decrypt(settings.slack_webhook_url)
                if webhook_url:
                    try:
                        await client.post(
                            webhook_url,
                            json={"text": f"*{notification.title}*\n{notification.body}"},
                        )
                    except Exception:
                        pass

            if "email" in channels and settings.email_to:
                if app_settings.smtp_host:
                    try:
                        msg = EmailMessage()
                        msg["From"] = app_settings.smtp_from
                        msg["To"] = settings.email_to
                        msg["Subject"] = notification.title
                        msg.set_content(f"{notification.body}")
                        msg.add_alternative(f"<p>{notification.body}</p>", subtype="html")

                        await aiosmtplib.send(
                            msg,
                            hostname=app_settings.smtp_host,
                            port=app_settings.smtp_port,
                            username=app_settings.smtp_user,
                            password=app_settings.smtp_password,
                            use_tls=app_settings.smtp_tls,
                        )
                    except Exception:
                        pass
                elif app_settings.resend_api_key:
                    try:
                        await client.post(
                            "https://api.resend.com/emails",
                            headers={"Authorization": f"Bearer {app_settings.resend_api_key}"},
                            json={
                                "from": "notifications@updates.refle.ai",
                                "to": settings.email_to,
                                "subject": notification.title,
                                "html": f"<p>{notification.body}</p>",
                            },
                        )
                    except Exception:
                        pass
