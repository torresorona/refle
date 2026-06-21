import asyncio
from refle_core.db import get_sessionmaker
from refle_core.models import OrgControl, Control, Organization, ControlStatus
from sqlalchemy import select
from refle_worker.celery_app import sync_all_connections


async def main():
    async with get_sessionmaker()() as session:
        # Get Cymbal Inc
        org = (
            (await session.execute(select(Organization).where(Organization.name == "Cymbal Inc")))
            .scalars()
            .first()
        )

        # Get CC6.1
        org_control = (
            (
                await session.execute(
                    select(OrgControl)
                    .join(Control, OrgControl.control_id == Control.id)
                    .where(OrgControl.organization_id == org.id, Control.code == "CC6.1")
                )
            )
            .scalars()
            .first()
        )

        print(f"Setting CC6.1 to passing (was {org_control.status})...")
        org_control.status = ControlStatus.passing
        await session.commit()

        print("Dispatching Celery task...")
        result = sync_all_connections.delay()
        print(f"Task dispatched! ID: {result.id}")


if __name__ == "__main__":
    asyncio.run(main())
