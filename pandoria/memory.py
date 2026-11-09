"""Memory interfaces. Storage engines are injected, not coupled to the kernel."""
from dataclasses import dataclass
from typing import Any, Protocol

@dataclass(frozen=True, slots=True)
class MemoryRecord:
    content: str
    memory_type: str
    user_id: str | None = None
    session_id: str | None = None
    metadata: dict[str, Any] | None = None

class MemoryStore(Protocol):
    async def recall(self, query: str, *, user_id: str | None,
                     session_id: str | None, limit: int = 8) -> list[MemoryRecord]: ...
    async def remember(self, record: MemoryRecord) -> None: ...

class NullMemory:
    """Safe no-op implementation used until a persistent store is configured."""
    async def recall(self, query: str, *, user_id: str | None,
                     session_id: str | None, limit: int = 8) -> list[MemoryRecord]:
        return []
    async def remember(self, record: MemoryRecord) -> None:
        return None
