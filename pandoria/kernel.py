"""PandorIA's top-level cognitive control plane."""
import time
from typing import Any

from pandoria.contracts import (
    CognitiveRequest, CognitiveResponse, ExecutionTrace, RiskLevel,
    TaskKind, TaskResult, TaskSpec,
)
from pandoria.integrations.base import AdapterRegistry
from pandoria.memory import MemoryStore, NullMemory
from pandoria.model_intelligence import ModelIntelligenceRouter, RoutingError
from pandoria.orchestration import AgentOrchestrator
from pandoria.planner import DependencyPlanner
from pandoria.policy import PolicyEngine
from pandoria.reasoning import ReasoningEngine
from pandoria.scheduler import BoundedScheduler
from pandoria.verifier import ResponseVerifier


class CognitiveKernel:
    """Coordinates reasoning, specialist agents, model routing and verification."""

    def __init__(
        self,
        *,
        registry: AdapterRegistry | None = None,
        memory: MemoryStore | None = None,
        max_concurrency: int = 8,
    ) -> None:
        self.registry = registry or AdapterRegistry()
        self.memory = memory or NullMemory()
        self.reasoning = ReasoningEngine()
        self.planner = DependencyPlanner()
        self.policy = PolicyEngine()
        self.scheduler = BoundedScheduler(max_concurrency=max_concurrency)
        self.router = ModelIntelligenceRouter(self.registry)
        self.orchestrator = AgentOrchestrator(
            self.router, max_concurrency=max_concurrency
        )
        self.verifier = ResponseVerifier()

    async def process(self, request: CognitiveRequest) -> CognitiveResponse:
        trace = ExecutionTrace(request_id=request.request_id)
        started = time.perf_counter()
        memories = await self.memory.recall(
            request.text, user_id=request.user_id, session_id=request.session_id
        )
        reasoning_plan = self.reasoning.plan(
            request.text, context_items=[record.content for record in memories]
        )
        trace.record(
            "reasoning",
            intent=reasoning_plan.context.intent,
            complexity=reasoning_plan.context.complexity,
            strategy=reasoning_plan.strategy,
            subtasks=len(reasoning_plan.subtasks),
            constraints=list(reasoning_plan.context.constraints),
        )

        agent_tasks: list[TaskSpec] = []
        for subtask in reasoning_plan.subtasks:
            capabilities = subtask.required_capabilities or frozenset({"text.generate"})
            agent_task = TaskSpec(
                task_id=subtask.id,
                description=subtask.objective,
                kind=TaskKind.MODEL,
                depends_on=subtask.depends_on,
                required_capabilities=capabilities,
                risk=RiskLevel.LOW,
                timeout_seconds=60,
                input_data={
                    "original_request": request.text,
                    "specialist_role": subtask.kind,
                    "expected_output": subtask.expected_output,
                },
            )
            decision = self.policy.evaluate(agent_task)
            if not decision.allowed:
                trace.warnings.append(
                    f"Agent task '{agent_task.task_id}' blocked: {decision.reason}"
                )
                verification = self.verifier.verify(
                    "", task_errors=[decision.reason]
                )
                return CognitiveResponse(
                    request.request_id,
                    "PandorIA blocked part of the plan under its current policy.",
                    verification,
                    trace,
                    status="blocked",
                )
            agent_tasks.append(agent_task)

        synthesis_task = TaskSpec(
            task_id="final_synthesis",
            description="Synthesize specialist outputs into the final answer.",
            kind=TaskKind.MODEL,
            required_capabilities=frozenset({"text.generate"}),
            risk=RiskLevel.LOW,
            timeout_seconds=60,
            input_data={"original_request": request.text},
        )
        decision = self.policy.evaluate(synthesis_task)
        if not decision.allowed:
            verification = self.verifier.verify("", task_errors=[decision.reason])
            return CognitiveResponse(
                request.request_id, "Final synthesis was blocked by policy.",
                verification, trace, status="blocked"
            )

        if not self.router.rank(synthesis_task):
            message = (
                "PandorIA's reasoning and orchestration layers are initialized, "
                "but no available model adapter provides 'text.generate'. "
                "Register a compatible provider to enable agent execution and synthesis."
            )
            trace.record("routing", candidates=0, selected=None)
            verification = self.verifier.verify(message, task_errors=[])
            trace.record(
                "verification", passed=verification.passed,
                confidence=verification.confidence
            )
            trace.record(
                "complete", elapsed_ms=(time.perf_counter() - started) * 1000
            )
            return CognitiveResponse(
                request.request_id, message, verification, trace,
                status="awaiting_provider"
            )

        report = await self.orchestrator.execute(
            agent_tasks,
            context={
                "request": request.text,
                "reasoning_plan": reasoning_plan.as_prompt_context(),
                "memories": [record.content for record in memories],
            },
        )
        trace.task_results.extend(item.result for item in report.executions)
        failed = [
            item for item in report.executions if not item.result.success
        ]
        trace.record(
            "orchestration",
            waves=report.waves,
            total_agents=len(report.executions),
            successful_agents=len(report.executions) - len(failed),
            failed_agents=len(failed),
            elapsed_ms=report.elapsed_ms,
            agents=[
                {
                    "task_id": item.task_id,
                    "role": item.role,
                    "provider": item.result.provider,
                    "success": item.result.success,
                    "attempts": list(item.provider_attempts),
                    "error": item.result.error,
                }
                for item in report.executions
            ],
        )

        synthesis_payload = {
            **dict(synthesis_task.input_data),
            "reasoning_plan": reasoning_plan.as_prompt_context(),
            "agent_outputs": report.outputs,
            "agent_failures": [
                {
                    "task_id": item.task_id,
                    "error": item.result.error,
                }
                for item in failed
            ],
            "synthesis_instruction": (
                "Combine the specialist outputs into one coherent answer. "
                "Respect the original request and constraints. Do not invent "
                "missing evidence. Explicitly disclose material gaps or failed "
                "specialists. Resolve disagreements only when the supplied outputs "
                "or evidence justify doing so."
            ),
        }
        try:
            outcome, elapsed = await self.scheduler.run(
                lambda: self.router.invoke(
                    synthesis_task, "generate", synthesis_payload
                ),
                synthesis_task.timeout_seconds,
            )
            synthesis_result = TaskResult(
                synthesis_task.task_id,
                True,
                output=outcome.output,
                provider=outcome.provider,
                elapsed_ms=elapsed,
                attempts=len(outcome.attempts),
            )
            trace.record(
                "synthesis",
                provider=outcome.provider,
                attempts=[
                    {
                        "provider": item.provider,
                        "success": item.success,
                        "elapsed_ms": item.elapsed_ms,
                        "error": item.error,
                    }
                    for item in outcome.attempts
                ],
            )
            answer = str(outcome.output)
        except RoutingError as exc:
            synthesis_result = TaskResult(
                synthesis_task.task_id,
                False,
                error=str(exc),
                attempts=len(exc.attempts),
            )
            answer = (
                "PandorIA completed its specialist orchestration, but every "
                "eligible synthesis provider failed."
            )
            trace.record(
                "synthesis",
                provider=None,
                attempts=[
                    {
                        "provider": item.provider,
                        "success": item.success,
                        "elapsed_ms": item.elapsed_ms,
                        "error": item.error,
                    }
                    for item in exc.attempts
                ],
            )
        except Exception as exc:
            synthesis_result = TaskResult(
                synthesis_task.task_id,
                False,
                error=f"{type(exc).__name__}: {exc}",
            )
            answer = "PandorIA could not complete final synthesis."
        trace.task_results.append(synthesis_result)

        task_errors = [
            f"{item.task_id}: {item.result.error}"
            for item in failed
        ]
        if not synthesis_result.success:
            task_errors.append(
                synthesis_result.error or "Final synthesis failed."
            )
        verification = self.verifier.verify(answer, task_errors=task_errors)
        trace.record(
            "verification",
            passed=verification.passed,
            confidence=verification.confidence,
            issues=list(verification.issues),
        )
        trace.record(
            "complete", elapsed_ms=(time.perf_counter() - started) * 1000
        )
        status = (
            "completed"
            if synthesis_result.success and not failed
            else "degraded"
        )
        return CognitiveResponse(
            request.request_id, answer, verification, trace, status=status
        )
