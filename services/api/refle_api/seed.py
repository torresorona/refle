"""Seed the SOC 2 control catalog from content/ into the database.

Run with: ``make seed`` (or ``uv run python -m refle_api.seed``). Idempotent.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import yaml
from refle_core.db import get_sessionmaker
from refle_core.models import Control, Framework
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

_DEFAULT_CONTENT = (
    Path(__file__).resolve().parents[3] / "content" / "frameworks" / "soc2" / "controls.yaml"
)


async def seed_soc2(session: AsyncSession, path: Path | None = None) -> dict[str, Any]:
    path = path or _DEFAULT_CONTENT
    data = yaml.safe_load(path.read_text())
    fw = data["framework"]

    framework = (
        await session.execute(select(Framework).where(Framework.key == fw["key"]))
    ).scalar_one_or_none()
    if framework is None:
        framework = Framework(key=fw["key"], name=fw["name"], version=fw.get("version"))
        session.add(framework)
        await session.flush()
    else:
        framework.name = fw["name"]
        framework.version = fw.get("version")

    existing = {
        c.code: c
        for c in (
            await session.execute(select(Control).where(Control.framework_id == framework.id))
        )
        .scalars()
        .all()
    }

    created = updated = 0
    for item in data["controls"]:
        control = existing.get(item["code"])
        description = (item.get("description") or "").strip() or None
        if control is None:
            session.add(
                Control(
                    framework_id=framework.id,
                    code=item["code"],
                    title=item["title"],
                    description=description,
                    category=item.get("category"),
                )
            )
            created += 1
        else:
            control.title = item["title"]
            control.description = description
            control.category = item.get("category")
            updated += 1

    await session.commit()
    return {"framework": framework.key, "created": created, "updated": updated}


async def _main() -> None:
    async with get_sessionmaker()() as session:
        result = await seed_soc2(session)
    print(
        f"seeded {result['framework']}: +{result['created']} created, {result['updated']} updated"
    )


def main() -> None:
    asyncio.run(_main())


if __name__ == "__main__":
    main()
