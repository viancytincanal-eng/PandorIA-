import asyncio
import pytest

from pandoria.contracts import TaskKind, TaskSpec
from pandoria.integrations.base import AdapterRegistry
from pandoria.model_intelligence import ModelIntelligenceRouter
from pandoria.orchestration import AgentOrchestrator


class FakeModel:
    name = "fake-model"
    capabilities = frozenset({"text.generate"})
    healthy = True
    routing_profile = {"quality": 0.8}

    def __init__(self):
        self.active = 0
        self.max_active = 0

    async def invoke(self, operation, payload, *, timeout_seconds):
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        await asyncio.sleep(0.01)
        self.active -= 1
        return {
            "task": payload["task"]["id"],
            "dependencies": payload["dependency_outputs"],
        }


def make_task(task_id, deps=()):
    return TaskSpec(
        task_id=task_id,
        description=f"Handle {task_id}",
        kind=TaskKind.MODEL,
        depends_on=deps,
        required_capabilities=frozenset({"text.generate"}),
        timeout_seconds=2,
    )


@pytest.mark.asyncio
async def test_independent_agents_run_in_parallel_and_dependencies_are_passed():
    registry = AdapterRegistry()
    model = FakeModel()
    registry.register(model)
    orchestrator = AgentOrchestrator(ModelIntelligenceRouter(registry), max_concurrency=3)
    report = await orchestrator.execute([
        make_task("alpha"),
        make_task("beta"),
        make_task("synthesis", ("alpha", "beta")),
    ], context={"request": "test request"})
    assert report.successful
    assert report.waves == 2
    assert model.max_active >= 2
    synthesis = report.outputs["synthesis"]
    assert set(synthesis["dependencies"]) == {"alpha", "beta"}


@pytest.mark.asyncio
async def test_failed_dependency_blocks_downstream_agent():
    registry = AdapterRegistry()
    registry.register(FakeModel())
    orchestrator = AgentOrchestrator(ModelIntelligenceRouter(registry))
    report = await orchestrator.execute([
        make_task("needs-web", ()),
        make_task("dependent", ("needs-web",)),
    ])
    assert report.outputs["dependent"]["dependencies"] == {}


def test_side_effecting_tool_tasks_are_rejected():
    registry = AdapterRegistry()
    orchestrator = AgentOrchestrator(ModelIntelligenceRouter(registry))
    tool_task = TaskSpec(
        task_id="send-email", description="Send email", kind=TaskKind.TOOL
    )
    with pytest.raises(ValueError, match="Side-effecting tools"):
        asyncio.run(orchestrator.execute([tool_task]))
