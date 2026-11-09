"""Stable contracts shared by cognitive layers and adapters."""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping
from uuid import uuid4

class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class TaskKind(StrEnum):
    REASON = "reason"
    MODEL = "model"
    TOOL = "tool"
    RETRIEVE = "retrieve"
    VERIFY = "verify"

@dataclass(frozen=True, slots=True)
class CognitiveRequest:
    text: str
    user_id: str | None = None
    session_id: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)
    request_id: str = field(default_factory=lambda: str(uuid4()))

@dataclass(frozen=True, slots=True)
class TaskSpec:
    task_id: str
    description: str
    kind: TaskKind = TaskKind.REASON
    depends_on: tuple[str, ...] = ()
    required_capabilities: frozenset[str] = frozenset()
    preferred_provider: str | None = None
    risk: RiskLevel = RiskLevel.LOW
    timeout_seconds: float = 30.0
    max_attempts: int = 1
    input_data: Mapping[str, Any] = field(default_factory=dict)

@dataclass(frozen=True, slots=True)
class TaskResult:
    task_id: str
    success: bool
    output: Any = None
    error: str | None = None
    provider: str | None = None
    elapsed_ms: float = 0.0
    attempts: int = 1

@dataclass(slots=True)
class ExecutionTrace:
    request_id: str
    stages: list[dict[str, Any]] = field(default_factory=list)
    task_results: list[TaskResult] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    def record(self, stage: str, **details: Any) -> None:
        self.stages.append({"stage": stage, **details})

@dataclass(frozen=True, slots=True)
class Verification:
    passed: bool
    confidence: float
    issues: tuple[str, ...] = ()
    evidence: tuple[str, ...] = ()

@dataclass(frozen=True, slots=True)
class CognitiveResponse:
    request_id: str
    answer: str
    verification: Verification
    trace: ExecutionTrace
    status: str = "completed"
