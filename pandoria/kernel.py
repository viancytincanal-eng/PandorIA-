"""PandorIA's top-level cognitive control plane."""
import time
from typing import Any
from pandoria.contracts import (CognitiveRequest, CognitiveResponse, ExecutionTrace,
    RiskLevel, TaskKind, TaskResult, TaskSpec)
from pandoria.integrations.base import AdapterRegistry
from pandoria.memory import MemoryStore, NullMemory
from pandoria.planner import DependencyPlanner
from pandoria.policy import PolicyEngine
from pandoria.reasoning import ReasoningEngine
from pandoria.scheduler import BoundedScheduler
from pandoria.verifier import ResponseVerifier


class CognitiveKernel:
    """Coordinates layered reasoning, planning, memory, integrations and verification."""
    def __init__(self, *, registry: AdapterRegistry | None = None,
                 memory: MemoryStore | None = None, max_concurrency: int = 8) -> None:
        self.registry = registry or AdapterRegistry()
        self.memory = memory or NullMemory()
        self.reasoning = ReasoningEngine()
        self.planner = DependencyPlanner()
        self.policy = PolicyEngine()
        self.scheduler = BoundedScheduler(max_concurrency=max_concurrency)
        self.verifier = ResponseVerifier()

    async def process(self, request: CognitiveRequest) -> CognitiveResponse:
        trace = ExecutionTrace(request_id=request.request_id)
        started = time.perf_counter()
        memories = await self.memory.recall(request.text, user_id=request.user_id,
                                            session_id=request.session_id)
        reasoning_plan = self.reasoning.plan(
            request.text, context_items=[record.content for record in memories])
        trace.record("reasoning", intent=reasoning_plan.context.intent,
                     complexity=reasoning_plan.context.complexity,
                     strategy=reasoning_plan.strategy,
                     subtasks=len(reasoning_plan.subtasks),
                     constraints=list(reasoning_plan.context.constraints))
        task = TaskSpec(task_id="respond", description="Respond using the reasoning plan.",
            kind=TaskKind.MODEL, required_capabilities=frozenset({"text.generate"}),
            risk=RiskLevel.LOW, timeout_seconds=60,
            input_data={"prompt": request.text,
                        "reasoning_plan": reasoning_plan.as_prompt_context(),
                        "memories": [record.content for record in memories]})
        waves = self.planner.order([task])
        trace.record("planning", tasks=sum(map(len, waves)), waves=len(waves))
        decision = self.policy.evaluate(task)
        if not decision.allowed:
            trace.warnings.append(decision.reason)
            verification = self.verifier.verify("", task_errors=[decision.reason])
            return CognitiveResponse(request.request_id,
                "I can't execute this request under the current policy.", verification, trace,
                status="blocked")
        candidates = self.registry.candidates(task.required_capabilities)
        if not candidates:
            message = ("PandorIA's cognitive core and layered reasoning planner are initialized, "
                "but no language-model adapter providing 'text.generate' is configured yet. "
                "Connect a model adapter to enable semantic reasoning and generation.")
            trace.record("routing", candidates=0, selected=None)
            verification = self.verifier.verify(message, task_errors=[])
            trace.record("verification", passed=verification.passed,
                         confidence=verification.confidence)
            trace.record("complete", elapsed_ms=(time.perf_counter() - started) * 1000)
            return CognitiveResponse(request.request_id, message, verification, trace,
                                     status="awaiting_provider")
        adapter = candidates[0]
        trace.record("routing", candidates=len(candidates), selected=adapter.name)
        async def invoke() -> Any:
            return await adapter.invoke("generate", dict(task.input_data),
                                        timeout_seconds=task.timeout_seconds)
        try:
            output, elapsed = await self.scheduler.run(invoke, task.timeout_seconds)
            result = TaskResult(task.task_id, True, output=output,
                                provider=adapter.name, elapsed_ms=elapsed)
        except Exception as exc:
            result = TaskResult(task.task_id, False,
                error=f"{type(exc).__name__}: {exc}", provider=adapter.name)
        trace.task_results.append(result)
        answer = str(result.output) if result.success else (
            "The selected model adapter failed. The failure was contained and recorded.")
        errors = [] if result.success else [result.error or "Unknown adapter failure."]
        verification = self.verifier.verify(answer, task_errors=errors)
        trace.record("verification", passed=verification.passed,
                     confidence=verification.confidence, issues=list(verification.issues))
        trace.record("complete", elapsed_ms=(time.perf_counter() - started) * 1000)
        return CognitiveResponse(request.request_id, answer, verification, trace,
            status="completed" if result.success else "degraded")
