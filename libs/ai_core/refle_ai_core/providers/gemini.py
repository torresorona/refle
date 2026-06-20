"""Google Gemini provider (default cloud backend) via the Generative Language API."""

from __future__ import annotations

from collections.abc import AsyncIterator

import httpx

from refle_ai_core.providers.base import Message

_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"


class GeminiProvider:
    def __init__(self, model: str, api_key: str | None) -> None:
        self.model = model
        self._api_key = api_key

    def _to_payload(self, messages: list[Message]) -> dict:
        contents: list[dict] = []
        system: str | None = None
        for message in messages:
            if message.role == "system":
                system = message.content
                continue
            role = "model" if message.role == "assistant" else "user"
            contents.append({"role": role, "parts": [{"text": message.content}]})
        body: dict = {"contents": contents}
        if system:
            body["systemInstruction"] = {"parts": [{"text": system}]}
        return body

    async def chat(self, messages: list[Message]) -> str:
        if not self._api_key:
            raise RuntimeError("GEMINI_API_KEY is not configured")
        url = f"{_BASE_URL}/models/{self.model}:generateContent"
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                url, params={"key": self._api_key}, json=self._to_payload(messages)
            )
            response.raise_for_status()
            data = response.json()
        return data["candidates"][0]["content"]["parts"][0]["text"]

    async def stream(self, messages: list[Message]) -> AsyncIterator[str]:
        # Token streaming (SSE) is a Phase 3 refinement; yield the full reply for now.
        yield await self.chat(messages)
