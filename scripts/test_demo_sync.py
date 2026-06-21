import asyncio
from refle_core.db import get_sessionmaker
from sqlalchemy import select
from refle_core.models import (
    OrgControl,
    Control,
    Connection,
    ConnectionStatus,
    ControlStatus,
    Organization,
)
from refle_integrations.engine import run_connection
from refle_integrations.connectors import register_builtin_connectors
from refle_ai_core.agents import register_builtin_agents
from refle_api.notify import dispatch_notifications


async def main():
    register_builtin_connectors()
    register_builtin_agents()
    async with get_sessionmaker()() as session:
        # Get Cymbal Inc
        org = (
            (await session.execute(select(Organization).where(Organization.name == "Cymbal Inc")))
            .scalars()
            .first()
        )

        if not org:
            print("Cymbal Inc not found")
            return

        # Get demo connection for Cymbal Inc
        conn = (
            (
                await session.execute(
                    select(Connection).where(
                        Connection.provider == "demo", Connection.organization_id == org.id
                    )
                )
            )
            .scalars()
            .first()
        )

        if not conn:
            print("No demo connection found for Cymbal Inc")
            return

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

        if not org_control:
            print("No org control found for CC6.1")
            return

        print(f"Setting CC6.1 to passing (was {org_control.status})...")
        org_control.status = ControlStatus.passing
        await session.commit()

        print("Running connection...")
        outcome = await run_connection(session, conn)

        if outcome.notifications:
            await dispatch_notifications(session, outcome.notifications)
            print("Dispatched notifications!")

        print(f"Sync outcome ok: {outcome.ok}")
        print(f"Failures: {outcome.failures}")
        print(f"Notifications: {len(outcome.notifications) if outcome.notifications else 0}")
        if outcome.error:
            print(f"Error: {outcome.error}")


if __name__ == "__main__":
    asyncio.run(main())
