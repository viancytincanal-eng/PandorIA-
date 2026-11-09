"""PandorIA's top-level cognitive control plane."""
import time
from pandoria.contracts import (
    CognitiveRequest, CognitiveResponse, ExecutionTrace, RiskLevel,
    TaskKind, TaskSpec,
)
from pandoria.integrations.base import AdapterRegistry
from pandoria.memory import MemoryStore, NullMemory
from pandoria.model_intelligence import ModelIntelligenceRouter
from pandoria.orchestration import MultiAgentOrchestrator
from pandoria.planner import DependencyPlanner
from pandoria.policy import PolicyEngine
from pandoria.reasoning import ReasoningEngine
from pandoria.scheduler import BoundedScheduler
from pandoria.verifier import ResponseVerifier


class CognitiveKernel:
    """Coordinates reasoning, specialist orchestration, models, memory and verification."""
    def __init__(self, *, registry: AdapterRegistry | None = None,
                 memory: MemoryStore | None = None, max_concurrency: int = 8) -> None:
        self.registry = registry or AdapterRegistry()
        self.memory = memory or NullMemory()
        self.reasoning = ReasoningEngine()
        self.planner = DependencyPlanner()
        self.policy = PolicyEngine()
        self.scheduler = BoundedScheduler(max_concurrency=max_concurrency)
        self.router = ModelIntelligenceRouter(self.registry)
        self.orchestrator = MultiAgentOrchestrator(
            self.router, self.planner, self.scheduler, self.policy
        )
        self.verifier = ResponseVerifier()

    async def process(self, request: CognitiveRequest) -> CognitiveResponse:
        trace = ExecutionTrace(request_id=request.request_id)
        started = time.perf_counter()
        memories = await self.memory.recall(
            request.text, user_id=request.user_id, session_id=request.session_id
        )
        memory_items = tuple(record.content for record in memories)
        reasoning_plan = self.reasoning.plan(
            request.text, context_items=memory_items
        )
        trace.record(
            "reasoning", intent=reasoning_plan.context.intent,
            complexity=reasoning_plan.context.complexity,
            strategy=reasoning_plan.strategy,
            subtasks=len(reasoning_plan.subtasks),
            constraints=list(reasoning_plan.context.constraints),
        )
        gate_task = TaskSpec(
            task_id="orchestrate",
            description="Coordinate the planned specialist workflow.",
            kind=TaskKind.MODEL,
            required_capabilities=frozenset({"text.generate"}),
            risk=RiskLevel.LOW,
            timeout_seconds=60,
            input_data={"prompt": request.text},
        )
        decision = self.policy.evaluate(gate_task)
        if not decision.allowed:
            trace.warnings.append(decision.reason)
            verification = self.verifier.verify("", task_errors=[decision.reason])
            return CognitiveResponse(
                request.request_id,
                "I can't execute this request under the current policy.",
                verification, trace, status="blocked",
            )
        if not self.router.rank(gate_task):
            message = (
                "PandorIA's cognitive core, reasoning planner and specialist "
                "orchestrator are initialized, but no available model adapter "
                "provides 'text.generate'. Register a compatible provider to "
                "enable semantic execution."
            )
            trace.record("routing", candidates=0, selected=None)
            verification = self.verifier.verify(message, task_errors=[])
            trace.record("verification", passed=verification.passed,
                         confidence=verification.confidence)
            trace.record("complete", elapsed_ms=(time.perf_counter() - started) * 1000)
            return CognitiveResponse(
                request.request_id, message, verification, trace,
                status="awaiting_provider",
            )

        result = await self.orchestrator.execute(
            reasoning_plan, request.text, context_items=memory_items
        )
        trace.task_results.extend(result.task_results)
        trace.record(
            "orchestration",
            executed=len(result.task_results),
            failed=list(result.failed_tasks),
            skipped=list(result.skipped_tasks),
            elapsed_ms=result.elapsed_ms,
        )
        for task_result in result.task_results:
            trace.record(
                "specialist",
                task_id=task_result.task_id,
                success=task_result.success,
                provider=task_result.provider,
                elapsed_ms=task_result.elapsed_ms,
                attempts=task_result.attempts,
                error=task_result.error,
            )
        errors = [
            f"{item.task_id}: {item.error or 'task failed'}"
            for item in result.task_results if not item.success
        ]
        verification = self.verifier.verify(result.answer, task_errors=errors)
        trace.record(
            "verification", passed=verification.passed,
            confidence=verification.confidence,
            issues=list(verification.issues),
        )
        trace.record("complete", elapsed_ms=(time.perf_counter() - started) * 1000)
        return CognitiveResponse(
            request.request_id, result.answer, verification, trace,
            status="completed" if not errors else "degraded",
        )
