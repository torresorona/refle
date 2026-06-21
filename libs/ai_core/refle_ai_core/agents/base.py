from typing import Any, Protocol


class AgentResult(Protocol):
    @property
    def output(self) -> str: ...

    @property
    def data(self) -> dict[str, Any] | None: ...


class SimpleAgentResult:
    def __init__(self, output: str, data: dict[str, Any] | None = None):
        self._output = output
        self._data = data

    @property
    def output(self) -> str:
        return self._output

    @property
    def data(self) -> dict[str, Any] | None:
        return self._data


class Agent(Protocol):
    @property
    def key(self) -> str: ...

    @property
    def name(self) -> str: ...

    @property
    def description(self) -> str: ...

    async def run(self, context: dict[str, Any], params: dict[str, Any]) -> AgentResult: ...
