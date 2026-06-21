import asyncio

from refle_api.notify import dispatch_notifications
from refle_core.db import get_sessionmaker
from refle_core.models import Notification, NotificationSetting, Organization, User
from sqlalchemy import select


async def main():
    async with get_sessionmaker()() as session:
        # Get the first user and their org
        user = (await session.execute(select(User))).scalars().first()
        if not user:
            print("No user found")
            return

        org = (await session.execute(select(Organization))).scalars().first()
        if not org:
            print("No organization found")
            return

        print(f"Triggering test email for {user.email} in org {org.name}...")

        # Configure settings
        setting = (
            await session.execute(
                select(NotificationSetting).where(NotificationSetting.organization_id == org.id)
            )
        ).scalar_one_or_none()

        if not setting:
            setting = NotificationSetting(organization_id=org.id, channels="")
            session.add(setting)

        setting.channels = "email"
        setting.email_to = user.email
        await session.commit()
        await session.refresh(setting)

        # Create a test notification
        notification = Notification(
            organization_id=org.id,
            type="test",
            title="Test Notification from Agent",
            body="This is a test notification to verify Resend email delivery is working correctly. If you see this, Phase 4 email integration is complete!",
            level="info",
        )
        session.add(notification)
        await session.commit()
        await session.refresh(notification)

        # Dispatch
        await dispatch_notifications(session, [notification])
        print("Dispatched successfully.")


if __name__ == "__main__":
    asyncio.run(main())
