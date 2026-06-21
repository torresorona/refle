from typing import Any

from refle_ai_core.agents.base import Agent, AgentResult, SimpleAgentResult
from refle_ai_core.gateway import AIGateway
from refle_ai_core.providers.base import Message


class DraftPolicyAgent(Agent):
    @property
    def key(self) -> str:
        return "draft-policy"

    @property
    def name(self) -> str:
        return "Draft Policy Agent"

    @property
    def description(self) -> str:
        return "Drafts a new policy document based on instructions and SOC 2 context."

    async def run(self, context: dict[str, Any], params: dict[str, Any]) -> AgentResult:
        instructions = params.get("instructions", "")
        name = params.get("name", "New Policy")
        in_scope_controls = context.get("controls", [])

        controls_text = "\n".join(
            f"- {c['code']}: {c['title']} ({c['description']})" for c in in_scope_controls
        )

        system_prompt = (
            "You are an expert compliance writer. Draft a formal, professional policy document "
            "for a B2B SaaS company aiming for SOC 2 compliance. "
            "Respond strictly in JSON matching the requested schema."
        )

        user_content = f"Policy Name: {name}\n"
        if instructions:
            user_content += f"Special Instructions: {instructions}\n"
        if controls_text:
            user_content += f"\nRelevant SOC 2 Controls to address:\n{controls_text}\n"

        template_body = context.get("template_body")
        if template_body:
            user_content += f"\nUse the following template as a structural baseline for the policy:\n{template_body}\n"

        attachment = context.get("attachment")
        if attachment:
            user_content += "\nAlso refer to the attached document/evidence as a primary source for the policy structure and contents."

        schema = {
            "type": "object",
            "properties": {
                "body": {
                    "type": "string",
                    "description": "The full markdown body of the policy.",
                }
            },
            "required": ["body"],
        }

        gateway = AIGateway().for_agent()
        messages = [
            Message(role="system", content=system_prompt),
            Message(
                role="user", content=user_content, attachments=[attachment] if attachment else None
            ),
        ]

        result = await gateway.provider.generate_structured(messages, schema)
        return SimpleAgentResult(output=result["body"], data=result)
