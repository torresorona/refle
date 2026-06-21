from typing import Any

from refle_ai_core.agents.base import Agent, AgentResult, SimpleAgentResult
from refle_ai_core.gateway import AIGateway
from refle_ai_core.providers.base import Message


class PostureSummaryAgent(Agent):
    @property
    def key(self) -> str:
        return "posture-summary"

    @property
    def name(self) -> str:
        return "Posture Summary Agent"

    @property
    def description(self) -> str:
        return "Summarizes posture changes into plain language and suggests remediation."

    async def run(self, context: dict[str, Any], params: dict[str, Any]) -> AgentResult:
        deltas = context.get("deltas", [])
        if not deltas:
            return SimpleAgentResult(
                output="No posture changes to summarize.",
                data={"body": "No posture changes to summarize."},
            )

        deltas_text = "\n".join(
            f"- {d['code']}: changed from {d['prev']} to {d['new']}" for d in deltas
        )

        system_prompt = (
            "You are an expert compliance assistant. Summarize the following posture changes "
            "into a brief, plain-language paragraph. If any controls are failing, briefly suggest "
            "next steps for remediation. "
            "Respond strictly in JSON matching the requested schema."
        )

        user_content = f"Posture Changes:\n{deltas_text}"

        schema = {
            "type": "object",
            "properties": {
                "body": {
                    "type": "string",
                    "description": "The plain-language summary of the changes.",
                }
            },
            "required": ["body"],
        }

        gateway = AIGateway().for_agent()
        messages = [
            Message(role="system", content=system_prompt),
            Message(role="user", content=user_content),
        ]

        try:
            result = await gateway.provider.generate_structured(messages, schema)
            return SimpleAgentResult(output=result["body"], data=result)
        except Exception as exc:
            # Fallback
            return SimpleAgentResult(
                output=f"Posture changed for: {', '.join(d['code'] for d in deltas)}. (AI summary unavailable: {exc})"
            )
