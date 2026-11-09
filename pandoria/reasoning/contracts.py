"""Typed contracts for the reasoning pipeline."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass(frozen=True, slots=True)
class Subtask:
    id: str
    objective: str
    kind: str = "analysis"
    depends_on: tuple[str, ...] = ()
    required_capabilities: frozenset[str] = frozenset()
    expected_output: str = "A concise result with supporting evidence."


@dataclass(frozen=True, slots=True)
class ReasoningContext:
    request: str
    normalized_request: str
    intent: str
    complexity: str
    constraints: tuple[str, ...] = ()
    context_items: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ReasoningPlan:
    context: ReasoningContext
    subtasks: tuple[Subtask, ...]
    strategy: str
    requires_external_evidence: bool = False
    requires_user_clarification: bool = False
    clarification_question: str | None = None
    warnings: tuple[str, ...] = ()

    def as_prompt_context(self) -> dict[str, Any]:
        return {
            "intent": self.context.intent,
            "complexity": self.context.complexity,
            "constraints": list(self.context.constraints),
            "strategy": self.strategy,
            "subtasks": [
                {"id": t.id, "objective": t.objective, "kind": t.kind,
                 "depends_on": list(t.depends_on), "expected_output": t.expected_output}
                for t in self.subtasks
            ],
            "requires_external_evidence": self.requires_external_evidence,
            "warnings": list(self.warnings),
        }
