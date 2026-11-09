import pytest
from pandoria.contracts import TaskKind, TaskSpec
from pandoria.integrations.base import AdapterRegistry
from pandoria.model_intelligence.router import ModelIntelligenceRouter, RoutingError

class FakeAdapter:
    capabilities = frozenset({"text.generate"})
    healthy = True
    def __init__(self, name, output=None, error=None, profile=None):
        self.name, self.output, self.error = name, output, error
        self.routing_profile = profile or {}
        self.calls = 0
    async def invoke(self, operation, payload, *, timeout_seconds):
        self.calls += 1
        if self.error:
            raise RuntimeError(self.error)
        return self.output

def task():
    return TaskSpec(task_id="answer", description="Answer", kind=TaskKind.MODEL,
        required_capabilities=frozenset({"text.generate"}), timeout_seconds=1)

def test_rank_prefers_higher_quality():
    registry = AdapterRegistry()
    registry.register(FakeAdapter("basic", "basic", profile={"quality": 0.3}))
    registry.register(FakeAdapter("strong", "strong", profile={"quality": 0.95}))
    assert ModelIntelligenceRouter(registry).rank(task())[0].name == "strong"

@pytest.mark.asyncio
async def test_failover_to_next_provider():
    registry = AdapterRegistry()
    registry.register(FakeAdapter("a-broken", error="offline"))
    registry.register(FakeAdapter("b-healthy", output="answer",
                                  profile={"quality": 0.9}))
    outcome = await ModelIntelligenceRouter(registry).invoke(task(), "generate", {})
    assert outcome.output == "answer"
    assert outcome.provider == "b-healthy"
    assert [a.success for a in outcome.attempts] == [False, True]

@pytest.mark.asyncio
async def test_all_failures_are_reported():
    registry = AdapterRegistry()
    registry.register(FakeAdapter("broken", error="offline"))
    with pytest.raises(RoutingError):
        await ModelIntelligenceRouter(registry).invoke(task(), "generate", {})

@pytest.mark.asyncio
async def test_circuit_opens_after_threshold():
    registry = AdapterRegistry()
    registry.register(FakeAdapter("unstable", error="offline"))
    router = ModelIntelligenceRouter(registry, circuit_failure_threshold=1,
                                     circuit_reset_seconds=60)
    with pytest.raises(RoutingError):
        await router.invoke(task(), "generate", {})
    assert router.health()["unstable"]["circuit"] == "open"
    assert router.rank(task()) == []

@pytest.mark.asyncio
async def test_router_exposes_observed_reliability_and_latency():
    registry = AdapterRegistry()
    registry.register(FakeAdapter("measured", output="ok"))
    router = ModelIntelligenceRouter(registry)
    for _ in range(3):
        await router.invoke(task(), "generate", {})
    metrics = router.health()["measured"]
    assert metrics["observed_reliability"] == 1.0
    assert metrics["observed_latency_ms"] is not None
