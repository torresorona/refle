"""Extension registries — the seam between community core and enterprise.

Community code registers built-in items (connectors, agents, auth providers).
The private ``refle-enterprise`` package, when installed, registers additional
items at startup *without modifying core*. Core only ever depends on these
registries, never on the concrete enterprise implementations.
"""

from __future__ import annotations


class Registry[T]:
    """A simple, name-keyed registry."""

    def __init__(self, kind: str) -> None:
        self._kind = kind
        self._items: dict[str, T] = {}

    def register(self, name: str, item: T, *, override: bool = False) -> T:
        if name in self._items and not override:
            raise ValueError(f"{self._kind} {name!r} is already registered")
        self._items[name] = item
        return item

    def get(self, name: str) -> T:
        try:
            return self._items[name]
        except KeyError:
            raise KeyError(f"unknown {self._kind}: {name!r}") from None

    def all(self) -> dict[str, T]:
        return dict(self._items)

    def names(self) -> list[str]:
        return sorted(self._items)

    def __contains__(self, name: object) -> bool:
        return name in self._items


# Global registries. Typed as ``object`` so this seam package stays
# dependency-free; the integrations / ai_core packages register concrete types.
connector_registry: Registry[object] = Registry("connector")
agent_registry: Registry[object] = Registry("agent")
auth_provider_registry: Registry[object] = Registry("auth_provider")
