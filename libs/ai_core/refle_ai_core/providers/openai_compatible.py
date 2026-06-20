"""OpenAI-compatible provider.

Backs both OpenAI itself and any OpenAI-compatible server — Ollama, vLLM,
LM Studio — which is how "sovereign" / local mode works.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import httpx

from refle_ai_core.providers.base import Message


class OpenAICompatibleProvider:
    def __init__(self, model: str, api_key: str | None, base_url: str) -> None:
        self.model = model
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")

    async def chat(self, messages: list[Message]) -> str:
        headers = {}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        payload = {
            "model": self.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
        }
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(
                f"{self._base_url}/chat/completions", headers=headers, json=payload
            )
            response.raise_for_status()
            data = response.json()
        return data["choices"][0]["message"]["content"]

    async def stream(self, messages: list[Message]) -> AsyncIterator[str]:
        yield await self.chat(messages)
