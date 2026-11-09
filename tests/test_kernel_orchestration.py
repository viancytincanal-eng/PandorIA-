import pytest

from pandoria.contracts import CognitiveRequest
from pandoria.integrations.base import AdapterRegistry
from pandoria.kernel import CognitiveKernel


class FakeModel:
    name = "kernel-test-model"
    capabilities = frozenset({"text.generate"})
    healthy = True
    routing_profile = {"quality": 0.8, "reliability": 0.99}

    async def invoke(self, operation, payload, *, timeout_seconds):
        task = payload["task"]
        return f"{task['role']} completed: {task['objective']}"


@pytest.mark.asyncio
async def test_kernel_executes_reasoning_plan_through_specialists():
    registry = AdapterRegistry()
    registry.register(FakeModel())
    kernel = CognitiveKernel(registry=registry, max_concurrency=3)

    response = await kernel.process(
        CognitiveRequest("Construye una aplicación modular con pruebas.")
    )

    assert response.status == "completed"
    assert response.answer.startswith("verify completed:")
    assert len(response.trace.task_results) == 4
    assert any(stage["stage"] == "orchestration" for stage in response.trace.stages)
    assert all(result.success for result in response.trace.task_results)


@pytest.mark.asyncio
async def test_kernel_reports_missing_model_provider_without_crashing():
    kernel = CognitiveKernel(registry=AdapterRegistry())
    response = await kernel.process(CognitiveRequest("Explícame qué es PandorIA."))

    assert response.status == "awaiting_provider"
    assert "text.generate" in response.answer
