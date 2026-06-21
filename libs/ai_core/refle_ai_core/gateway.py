"""The single entry point AI features use, regardless of the underlying model.

Selecting a provider is a per-deployment config change (``REFLE_AI_PROVIDER``):
``gemini`` (default), ``openai``, or ``local`` for sovereign mode.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass

from refle_ai_core.config import AISettings, get_ai_settings
from refle_ai_core.providers.base import ChatProvider, Message
from refle_ai_core.providers.gemini import GeminiProvider
from refle_ai_core.providers.openai_compatible import OpenAICompatibleProvider

_OPENAI_BASE_URL = "https://api.openai.com/v1"


@dataclass
class GatewayInfo:
    provider: str
    model: str
    sovereign: bool


def build_provider(settings: AISettings) -> ChatProvider:
    if settings.provider == "gemini":
        return GeminiProvider(model=settings.model, api_key=settings.gemini_api_key)
    if settings.provider == "openai":
        return OpenAICompatibleProvider(
            model=settings.model,
            api_key=settings.openai_api_key,
            base_url=_OPENAI_BASE_URL,
        )
    if settings.provider == "local":
        return OpenAICompatibleProvider(
            model=settings.local_model,
            api_key=None,
            base_url=settings.local_base_url,
        )
    raise ValueError(f"unknown AI provider: {settings.provider!r}")


class AIGateway:
    def __init__(self, settings: AISettings | None = None) -> None:
        self.settings = settings or get_ai_settings()
        self.provider = build_provider(self.settings)

    @property
    def info(self) -> GatewayInfo:
        return GatewayInfo(
            provider=self.settings.provider,
            model=self.provider.model,
            sovereign=self.settings.provider == "local",
        )

    def for_agent(self) -> AIGateway:
        agent_settings = self.settings.model_copy(update={"model": self.settings.agent_model})
        return AIGateway(agent_settings)

    async def chat(self, messages: list[Message]) -> str:
        return await self.provider.chat(messages)

    async def stream(self, messages: list[Message]) -> AsyncIterator[str]:
        async for chunk in self.provider.stream(messages):
            yield chunk
