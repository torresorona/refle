from typing import Any

from refle_ai_core.agents.base import Agent, AgentResult, SimpleAgentResult
from refle_ai_core.gateway import AIGateway
from refle_ai_core.providers.base import Message


class SspNarrativeAgent(Agent):
    """Drafts a System Security Plan narrative from a readiness summary.

    Optional/additive: when no LLM is available it returns a templated narrative
    so the audit package still builds in Hosted Core / sovereign mode.
    """

    @property
    def key(self) -> str:
        return "ssp-narrative"

    @property
    def name(self) -> str:
        return "SSP Narrative Agent"

    @property
    def description(self) -> str:
        return "Writes a System Security Plan narrative section from readiness data."

    @property
    def model(self) -> str:
        return AIGateway().settings.agent_model

    async def run(self, context: dict[str, Any], params: dict[str, Any]) -> AgentResult:
        summary = context.get("summary", "")

        system_prompt = (
            "You are an expert compliance writer. Using the readiness summary, write a "
            "concise System Security Plan (SSP) narrative section in markdown describing the "
            "entity's control posture and how it addresses SOC 2. "
            "Respond strictly in JSON matching the requested schema."
        )
        schema = {
            "type": "object",
            "properties": {"body": {"type": "string"}},
            "required": ["body"],
        }
        gateway = AIGateway().for_agent()
        messages = [
            Message(role="system", content=system_prompt),
            Message(role="user", content=f"Readiness summary:\n{summary}"),
        ]
        try:
            result = await gateway.provider.generate_structured(messages, schema)
            return SimpleAgentResult(output=result["body"], data=result)
        except Exception:  # noqa: BLE001 - templated narrative when no LLM is available
            body = (
                "# System Security Plan (Narrative)\n\n"
                "_Generated without an AI model; based on current readiness data._\n\n"
                f"{summary}"
            )
            return SimpleAgentResult(output=body, data={"fallback": True})
