"""Dependency-aware multi-agent orchestration over model adapters."""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Any, Mapping

from pandoria.contracts import TaskKind, TaskResult, TaskSpec
from pandoria.model_intelligence import ModelIntelligenceRouter, RoutingError
from pandoria.planner import DependencyPlanner


@dataclass(frozen=True, slots=True)
class AgentExecution:
    task_id: str
    role: str
    result: TaskResult
    provider_attempts: tuple[dict[str, Any], ...] = ()


@dataclass(frozen=True, slots=True)
class OrchestrationReport:
    executions: tuple[AgentExecution, ...]
    waves: int
    elapsed_ms: float

    @property
    def successful(self) -> bool:
        return bool(self.executions) and all(
            item.result.success for item in self.executions
        )

    @property
    def outputs(self) -> dict[str, Any]:
        return {
            item.task_id: item.result.output
            for item in self.executions
            if item.result.success
        }


class AgentOrchestrator:
    """Runs independent specialist tasks concurrently and respects dependencies.

    This layer deliberately refuses side-effecting TOOL tasks. Tool execution needs
    a separate policy/idempotency boundary and must not inherit model failover rules.
    """
    _OPERATIONS = {
        TaskKind.MODEL: "generate",
        TaskKind.REASON: "reason",
        TaskKind.RETRIEVE: "retrieve",
        TaskKind.VERIFY: "verify",
    }

    def __init__(
        self,
        router: ModelIntelligenceRouter,
        *,
        max_concurrency: int = 4,
        planner: DependencyPlanner | None = None,
    ) -> None:
        if max_concurrency < 1:
            raise ValueError("max_concurrency must be positive")
        self.router = router
        self.max_concurrency = max_concurrency
        self.planner = planner or DependencyPlanner()
        self._semaphore = asyncio.Semaphore(max_concurrency)

    async def execute(
        self,
        tasks: list[TaskSpec],
        *,
        context: Mapping[str, Any] | None = None,
    ) -> OrchestrationReport:
        started = time.perf_counter()
        if not tasks:
            return OrchestrationReport((), 0, 0.0)
        for task in tasks:
            if task.kind not in self._OPERATIONS:
                raise ValueError(
                    f"Task '{task.task_id}' has unsupported kind '{task.kind}'. "
                    "Side-effecting tools require a separate governed executor."
                )
            if task.timeout_seconds <= 0:
                raise ValueError(f"Task '{task.task_id}' timeout must be positive.")
        waves = self.planner.order(tasks)
        completed: dict[str, AgentExecution] = {}
        base_context = dict(context or {})

        async def run_one(task: TaskSpec) -> AgentExecution:
            failed_dependencies = [
                dependency for dependency in task.depends_on
                if dependency not in completed or not completed[dependency].result.success
            ]
            if failed_dependencies:
                reason = "Blocked by unsuccessful dependencies: " + ", ".join(
                    failed_dependencies
                )
                return AgentExecution(
                    task.task_id, task.kind.value,
                    TaskResult(task.task_id, False, error=reason, attempts=0),
                )
            dependency_outputs = {
                dependency: completed[dependency].result.output
                for dependency in task.depends_on
            }
            payload = {
                **base_context,
                "task": {
                    "id": task.task_id,
                    "role": task.kind.value,
                    "objective": task.description,
                    "input": dict(task.input_data),
                },
                "dependency_outputs": dependency_outputs,
            }
            operation = self._OPERATIONS[task.kind]
            attempts: tuple[dict[str, Any], ...] = ()
            async with self._semaphore:
                try:
                    outcome = await asyncio.wait_for(
                        self.router.invoke(task, operation, payload),
                        timeout=task.timeout_seconds,
                    )
                    attempts = tuple({
                        "provider": item.provider,
                        "success": item.success,
                        "elapsed_ms": item.elapsed_ms,
                        "error": item.error,
                    } for item in outcome.attempts)
                    result = TaskResult(
                        task.task_id, True, output=outcome.output,
                        provider=outcome.provider, elapsed_ms=outcome.elapsed_ms,
                        attempts=len(outcome.attempts),
                    )
                except RoutingError as exc:
                    attempts = tuple({
                        "provider": item.provider,
                        "success": item.success,
                        "elapsed_ms": item.elapsed_ms,
                        "error": item.error,
                    } for item in exc.attempts)
                    result = TaskResult(
                        task.task_id, False, error=str(exc),
                        attempts=len(exc.attempts),
                    )
                except Exception as exc:
                    result = TaskResult(
                        task.task_id, False,
                        error=f"{type(exc).__name__}: {exc}",
                    )
            return AgentExecution(task.task_id, task.kind.value, result, attempts)

        for wave in waves:
            wave_results = await asyncio.gather(*(run_one(task) for task in wave))
            for execution in wave_results:
                completed[execution.task_id] = execution

        ordered = tuple(completed[task.task_id] for task in tasks)
        return OrchestrationReport(
            executions=ordered,
            waves=len(waves),
            elapsed_ms=(time.perf_counter() - started) * 1000,
        )
