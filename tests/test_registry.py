from pandoria.integrations.base import AdapterRegistry

class FakeAdapter:
    name = "fake"
    capabilities = frozenset({"text.generate", "json"})
    healthy = True

def test_registry_routes_by_capability_and_health():
    registry = AdapterRegistry()
    adapter = FakeAdapter()
    registry.register(adapter)
    assert [item.name for item in registry.candidates(frozenset({"text.generate"}))] == ["fake"]
    assert registry.candidates(frozenset({"image.generate"})) == []
    adapter.healthy = False
    assert registry.candidates(frozenset({"text.generate"})) == []
