"""OpenAI-compatible provider.

Backs both OpenAI itself and any OpenAI-compatible server — Ollama, vLLM,
LM Studio — which is how "sovereign" / local mode works.
"""

from __future__ import annotations

import json
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

    async def generate_structured(self, messages: list[Message], schema: dict) -> dict:
        schema_str = json.dumps(schema)
        messages_copy = list(messages)
        messages_copy.append(
            Message(
                role="user", content=f"Respond strictly in JSON matching this schema: {schema_str}"
            )
        )
        headers = {}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        payload = {
            "model": self.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages_copy],
            "response_format": {"type": "json_object"},
        }
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(
                f"{self._base_url}/chat/completions", headers=headers, json=payload
            )
            response.raise_for_status()
            data = response.json()
        text = data["choices"][0]["message"]["content"]
        # Basic cleanup in case model wrapped it in markdown codeblocks
        text = text.strip()
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        return json.loads(text.strip())

    async def stream(self, messages: list[Message]) -> AsyncIterator[str]:
        yield await self.chat(messages)
