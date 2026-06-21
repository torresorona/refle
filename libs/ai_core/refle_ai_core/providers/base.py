"""Provider interface shared by all model backends."""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Literal, Protocol

Role = Literal["system", "user", "assistant"]


@dataclass
class Attachment:
    mime_type: str
    data: bytes


@dataclass
class Message:
    role: Role
    content: str
    attachments: list[Attachment] | None = None


class ChatProvider(Protocol):
    model: str

    async def chat(self, messages: list[Message]) -> str: ...

    async def generate_structured(self, messages: list[Message], schema: dict) -> dict: ...

    def stream(self, messages: list[Message]) -> AsyncIterator[str]: ...
