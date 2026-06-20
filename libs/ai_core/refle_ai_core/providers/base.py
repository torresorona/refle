"""Provider interface shared by all model backends."""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Literal, Protocol

Role = Literal["system", "user", "assistant"]


@dataclass
class Message:
    role: Role
    content: str


class ChatProvider(Protocol):
    model: str

    async def chat(self, messages: list[Message]) -> str: ...

    def stream(self, messages: list[Message]) -> AsyncIterator[str]: ...
