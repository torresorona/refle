"""Run an agent and persist an ``AiRun`` audit record around it.

Shared by the API (e.g. the draft-policy endpoint) and the sync engine
(posture-summary) so that *every* agent execution is auditable, per the Phase 4
design. The ``agent`` is duck-typed (``key``, ``run``, optional ``model``) to
keep this module free of any dependency on ``ai_core``.
"""

from __future__ import annotations

import uuid
from typing import Any, Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from refle_core.models import AiRun, AiRunStatus


class Runnable(Protocol):
    @property
    def key(self) -> str: ...

    async def run(self, context: dict[str, Any], params: dict[str, Any]) -> Any: ...


async def record_agent_run(
    session: AsyncSession,
    *,
    organization_id: uuid.UUID,
    agent: Runnable,
    context: dict[str, Any],
    params: dict[str, Any],
    model: str | None = None,
    input_record: dict[str, Any] | None = None,
    commit_on_failure: bool = True,
) -> tuple[Any, AiRun]:
    """Create an ``AiRun``, run the agent, and record the outcome.

    Returns ``(agent_result, ai_run)``. The caller commits on success. On agent
    failure the run is marked ``failed`` (committed when ``commit_on_failure``)
    and the exception is re-raised so the caller can surface it.
    """
    resolved_model = model or getattr(agent, "model", None) or "unknown"
    ai_run = AiRun(
        organization_id=organization_id,
        agent_key=agent.key,
        input=input_record if input_record is not None else dict(params),
        status=AiRunStatus.running,
        model=resolved_model,
    )
    session.add(ai_run)
    await session.flush()

    try:
        result = await agent.run(context, params)
    except Exception as exc:  # noqa: BLE001 - record the failure, then propagate
        ai_run.status = AiRunStatus.failed
        ai_run.error = str(exc)
        if commit_on_failure:
            await session.commit()
        raise

    ai_run.output = result.output
    ai_run.status = AiRunStatus.succeeded
    return result, ai_run
