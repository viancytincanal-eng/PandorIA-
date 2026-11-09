import pytest

from pandoria.contracts import CognitiveRequest
from pandoria.integrations.base import AdapterRegistry
from pandoria.kernel import CognitiveKernel


class MultiCapabilityAdapter:
    name = "test-specialist"
    capabilities = frozenset({"text.generate", "web.search"})
    healthy = True
    routing_profile = {"quality": 0.9, "reliability": 1.0}

    async def invoke(self, operation, payload, *, timeout_seconds):
        if operation == "search":
            return "Evidence gathered from the configured search source."
        if operation == "generate" and "task" in payload:
            return f"Specialist result for {payload['task']['id']}."
        if operation == "generate":
            return "Final synthesized answer."
        raise AssertionError(f"Unexpected operation: {operation}")


@pytest.mark.asyncio
async def test_kernel_runs_research_agents_and_synthesizes():
    registry = AdapterRegistry()
    registry.register(MultiCapabilityAdapter())
    kernel = CognitiveKernel(registry=registry)
    response = await kernel.process(
        CognitiveRequest("Investiga y compara las opciones disponibles.")
    )
    assert response.answer == "Final synthesized answer."
    assert response.status == "completed"
    orchestration = next(
        stage for stage in response.trace.stages
        if stage["stage"] == "orchestration"
    )
    assert orchestration["total_agents"] == 3
    assert orchestration["failed_agents"] == 0
    assert any(
        attempt["provider"] == "test-specialist" and attempt["success"]
        for agent in orchestration["agents"]
        for attempt in agent["attempts"]
    )
    assert any(
        result.task_id == "final_synthesis" and result.success
        for result in response.trace.task_results
    )


@pytest.mark.asyncio
async def test_kernel_waits_for_text_provider_when_none_is_registered():
    kernel = CognitiveKernel()
    response = await kernel.process(CognitiveRequest("Explica la gravedad."))
    assert response.status == "awaiting_provider"
    assert "no available model adapter" in response.answer
