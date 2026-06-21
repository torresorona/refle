from refle_extensions.registry import agent_registry

from refle_ai_core.agents.draft_policy import DraftPolicyAgent
from refle_ai_core.agents.posture_summary import PostureSummaryAgent


def register_builtin_agents() -> None:
    agent_registry.register("draft-policy", DraftPolicyAgent())
    agent_registry.register("posture-summary", PostureSummaryAgent())
