"""Capability-based adapter registry with explicit isolation boundaries."""
from dataclasses import dataclass
from typing import Any, Protocol

@dataclass(frozen=True, slots=True)
class Capability:
    name: str
    description: str = ""
    side_effecting: bool = False

class Adapter(Protocol):
    name: str
    capabilities: frozenset[str]
    healthy: bool
    async def invoke(self, operation: str, payload: dict[str, Any],
                     *, timeout_seconds: float) -> Any: ...

class AdapterRegistry:
    def __init__(self) -> None:
        self._adapters: dict[str, Adapter] = {}
    def register(self, adapter: Adapter) -> None:
        if adapter.name in self._adapters:
            raise ValueError(f"Adapter already registered: {adapter.name}")
        self._adapters[adapter.name] = adapter
    def unregister(self, name: str) -> None:
        self._adapters.pop(name, None)
    def candidates(self, required: frozenset[str]) -> list[Adapter]:
        return sorted((a for a in self._adapters.values()
                       if a.healthy and required <= a.capabilities), key=lambda a: a.name)
    def get(self, name: str) -> Adapter | None:
        return self._adapters.get(name)
    def health(self) -> dict[str, bool]:
        return {name: adapter.healthy for name, adapter in self._adapters.items()}
