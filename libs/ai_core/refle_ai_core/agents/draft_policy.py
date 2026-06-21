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

    @property
    def model(self) -> str:
        return AIGateway().settings.agent_model

    async def run(self, context: dict[str, Any], params: dict[str, Any]) -> AgentResult:
        instructions = params.get("instructions", "")
        name = params.get("name", "New Policy")
        in_scope_controls = context.get("controls", [])
        template_body = context.get("template_body")

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
        if template_body:
            user_content += (
                "\nUse the following template as a structural baseline for the policy:\n"
                f"{template_body}\n"
            )

        attachment = context.get("attachment")
        if attachment:
            user_content += (
                "\nAlso refer to the attached document/evidence as a primary source "
                "for the policy structure and contents."
            )

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

        try:
            result = await gateway.provider.generate_structured(messages, schema)
            return SimpleAgentResult(output=result["body"], data=result)
        except Exception as exc:  # noqa: BLE001 - degrade to a templated draft when no LLM
            body = self._fallback_body(name, instructions, template_body, controls_text, exc)
            return SimpleAgentResult(output=body, data={"body": body, "fallback": True})

    @staticmethod
    def _fallback_body(
        name: str,
        instructions: str,
        template_body: str | None,
        controls_text: str,
        exc: Exception,
    ) -> str:
        """A usable, human-editable starting point when AI drafting is unavailable.

        Prefers the chosen template verbatim; otherwise a minimal skeleton that
        lists the in-scope controls so a reviewer can flesh it out.
        """
        if template_body:
            base = template_body
        else:
            sections = [f"# {name}", "", "## Purpose", "_Describe the purpose of this policy._", ""]
            if controls_text:
                sections += ["## Controls addressed", controls_text, ""]
            base = "\n".join(sections)
        note = (
            "\n\n> This draft was generated without an AI model "
            f"(AI drafting unavailable: {exc}). Review and edit before publishing."
        )
        if instructions:
            note = f"\n\n> Drafting instructions: {instructions}" + note
        return base + note
