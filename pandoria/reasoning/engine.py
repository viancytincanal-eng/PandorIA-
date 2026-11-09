"""Composable reasoning pipeline with explicit stage boundaries."""
from __future__ import annotations
from collections.abc import Callable, Sequence
from pandoria.reasoning.contracts import ReasoningContext, ReasoningPlan
from pandoria.reasoning.stages import normalize, classify_intent, estimate_complexity, extract_constraints, decompose


class ReasoningEngine:
    """Builds an auditable work plan before model/tool execution.

    The default stages are deterministic and inexpensive. Deep semantic reasoning is
    delegated to configured model adapters, while this engine handles structure,
    constraints, dependencies and review boundaries.
    """
    def __init__(self, *, max_request_chars: int = 50_000) -> None:
        if max_request_chars < 1:
            raise ValueError("max_request_chars must be positive")
        self.max_request_chars = max_request_chars

    def plan(self, request: str, *, context_items: Sequence[str] = ()) -> ReasoningPlan:
        if not isinstance(request, str) or not request.strip():
            raise ValueError("A non-empty request is required.")
        if len(request) > self.max_request_chars:
            raise ValueError(f"Request exceeds the {self.max_request_chars}-character limit.")
        normalized = normalize(request)
        intent = classify_intent(normalized)
        complexity = estimate_complexity(normalized)
        constraints = extract_constraints(normalized)
        context = ReasoningContext(
            request=request,
            normalized_request=normalized,
            intent=intent,
            complexity=complexity,
            constraints=constraints,
            context_items=tuple(context_items),
        )
        subtasks = decompose(context)
        strategy = {
            "research": "evidence_first",
            "build": "specify_design_implement_verify",
            "plan": "goal_constraints_sequence_review",
            "explain": "progressive_explanation",
            "creative": "diverge_then_refine",
            "general": "analyze_solve_review",
        }.get(intent, "analyze_solve_review")
        return ReasoningPlan(
            context=context,
            subtasks=subtasks,
            strategy=strategy,
            requires_external_evidence=intent == "research",
        )
