"""PandorIA's top-level cognitive control plane."""
import time
from pandoria.contracts import (
    CognitiveRequest, CognitiveResponse, ExecutionTrace, RiskLevel,
    TaskKind, TaskSpec,
)
from pandoria.integrations.base import AdapterRegistry
from pandoria.memory import MemoryStore, NullMemory
from pandoria.model_intelligence import ModelIntelligenceRouter
from pandoria.orchestration import AgentOrchestrator
from pandoria.planner import DependencyPlanner
from pandoria.policy import PolicyEngine
from pandoria.reasoning import ReasoningEngine
from pandoria.verifier import ResponseVerifier


_SPECIALIST_GUIDANCE = {
    "analysis": "Identify the goal, assumptions, constraints and unknowns.",
    "research": "Gather evidence using only connected capabilities; never invent citations.",
    "design": "Propose a modular design, interfaces, trade-offs and failure boundaries.",
    "implementation": "Produce a concrete implementation consistent with requirements.",
    "solve": "Solve the assigned objective using context and explicit constraints.",
    "synthesis": "Combine dependency outputs and distinguish facts from uncertainty.",
    "verification": "Audit the work for contradictions, omissions and unsupported claims.",
}


class CognitiveKernel:
    """Coordinates reasoning, specialist orchestration, models, memory and verification."""
    def __init__(self, *, registry: AdapterRegistry | None = None,
                 memory: MemoryStore | None = None, max_concurrency: int = 8) -> None:
        self.registry = registry or AdapterRegistry()
        self.memory = memory or NullMemory()
        self.reasoning = ReasoningEngine()
        self.planner = DependencyPlanner()
        self.policy = PolicyEngine()
        self.router = ModelIntelligenceRouter(self.registry)
        self.orchestrator = AgentOrchestrator(
            self.router, max_concurrency=max_concurrency, planner=self.planner
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

        task_specs = []
        for subtask in reasoning_plan.subtasks:
            kind = {
                "research": TaskKind.RETRIEVE,
                "verification": TaskKind.VERIFY,
                "review": TaskKind.VERIFY,
                "implementation": TaskKind.MODEL,
            }.get(subtask.kind, TaskKind.REASON)
            capabilities = set(subtask.required_capabilities)
            capabilities.add("text.generate")
            task_specs.append(TaskSpec(
                task_id=subtask.id,
                description=subtask.objective,
                kind=kind,
                depends_on=subtask.depends_on,
                required_capabilities=frozenset(capabilities),
                risk=RiskLevel.LOW,
                timeout_seconds=60,
                max_attempts=1,
                input_data={
                    "original_request": request.text,
                    "specialist_instruction": _SPECIALIST_GUIDANCE.get(
                        subtask.kind, "Complete the assigned objective carefully."
                    ),
                    "expected_output": subtask.expected_output,
                    "reasoning_strategy": reasoning_plan.strategy,
                },
            ))

        report = await self.orchestrator.execute(
            task_specs,
            context={
                "request": request.text,
                "reasoning_plan": reasoning_plan.as_prompt_context(),
                "context_items": list(memory_items),
            },
        )
        results = [execution.result for execution in report.executions]
        trace.task_results.extend(results)
        failed = [item for item in results if not item.success]
        skipped = [
            item.task_id for item in failed
            if item.error and "Blocked by unsuccessful dependencies" in item.error
        ]
        trace.record(
            "orchestration",
            executed=len(results),
            waves=report.waves,
            failed=[item.task_id for item in failed],
            skipped=skipped,
            elapsed_ms=report.elapsed_ms,
        )
        for execution in report.executions:
            trace.record(
                "specialist",
                task_id=execution.task_id,
                role=execution.role,
                success=execution.result.success,
                provider=execution.result.provider,
                elapsed_ms=execution.result.elapsed_ms,
                attempts=execution.result.attempts,
                provider_attempts=list(execution.provider_attempts),
                error=execution.result.error,
            )

        dependent_ids = {
            dependency for item in task_specs for dependency in item.depends_on
        }
        terminal_ids = [
            item.task_id for item in task_specs if item.task_id not in dependent_ids
        ]
        terminal_outputs = [
            str(report.outputs[item]) for item in terminal_ids
            if item in report.outputs and report.outputs[item] is not None
        ]
        answer = "\n\n".join(terminal_outputs).strip()
        if not answer:
            answer = (
                "PandorIA could not complete the planned specialist workflow. "
                "Inspect the execution trace for failed tasks or unavailable capabilities."
            )
        errors = [
            f"{item.task_id}: {item.error or 'task failed'}" for item in failed
        ]
        verification = self.verifier.verify(answer, task_errors=errors)
        trace.record(
            "verification", passed=verification.passed,
            confidence=verification.confidence,
            issues=list(verification.issues),
        )
        trace.record("complete", elapsed_ms=(time.perf_counter() - started) * 1000)
        return CognitiveResponse(
            request.request_id, answer, verification, trace,
            status="completed" if not errors else "degraded",
        )
