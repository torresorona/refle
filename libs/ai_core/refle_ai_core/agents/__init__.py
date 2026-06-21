from refle_extensions.registry import agent_registry

from refle_ai_core.agents.draft_policy import DraftPolicyAgent
from refle_ai_core.agents.posture_summary import PostureSummaryAgent
from refle_ai_core.agents.ssp_narrative import SspNarrativeAgent


def register_builtin_agents() -> None:
    for key, agent in (
        ("draft-policy", DraftPolicyAgent()),
        ("posture-summary", PostureSummaryAgent()),
        ("ssp-narrative", SspNarrativeAgent()),
    ):
        if key not in agent_registry:
            agent_registry.register(key, agent)
