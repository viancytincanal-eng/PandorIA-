"""Capability-aware model selection, bounded failover and provider health."""
from __future__ import annotations
import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, Mapping
from pandoria.contracts import TaskSpec
from pandoria.integrations.base import AdapterRegistry

@dataclass(frozen=True, slots=True)
class ProviderAttempt:
    provider: str
    success: bool
    elapsed_ms: float
    error: str | None = None

@dataclass(frozen=True, slots=True)
class RoutingOutcome:
    output: Any
    provider: str
    elapsed_ms: float
    attempts: tuple[ProviderAttempt, ...]
    candidates_considered: int

class RoutingError(RuntimeError):
    def __init__(self, attempts: tuple[ProviderAttempt, ...]) -> None:
        self.attempts = attempts
        details = "; ".join(f"{a.provider}: {a.error or 'failed'}" for a in attempts)
        super().__init__(f"All eligible model providers failed. {details}")

@dataclass(slots=True)
class _Circuit:
    failures: int = 0
    opened_until: float = 0.0
    successes: int = 0

@dataclass(slots=True)
class _ProviderRuntime:
    semaphore: asyncio.Semaphore
    circuit: _Circuit = field(default_factory=_Circuit)

class ModelIntelligenceRouter:
    """Ranks compatible adapters and fails over without vendor coupling.

    Optional adapter.routing_profile fields: quality, reliability, latency_ms,
    cost and max_concurrency. Quality, reliability and cost are normalized 0..1.
    """
    def __init__(self, registry: AdapterRegistry, *,
                 default_provider_concurrency: int = 2,
                 circuit_failure_threshold: int = 3,
                 circuit_reset_seconds: float = 30.0) -> None:
        if default_provider_concurrency < 1 or circuit_failure_threshold < 1:
            raise ValueError("Concurrency and circuit threshold must be positive")
        self.registry = registry
        self.default_provider_concurrency = default_provider_concurrency
        self.circuit_failure_threshold = circuit_failure_threshold
        self.circuit_reset_seconds = circuit_reset_seconds
        self._runtime: dict[str, _ProviderRuntime] = {}

    def rank(self, task: TaskSpec) -> list[Any]:
        now = time.monotonic()
        ranked = []
        for adapter in self.registry.candidates(task.required_capabilities):
            runtime = self._runtime_for(adapter)
            if runtime.circuit.opened_until > now:
                continue
            score = self._score(self._profile(adapter), task)
            if task.preferred_provider == adapter.name:
                score += 0.12
            ranked.append((score, adapter.name, adapter))
        ranked.sort(key=lambda item: (-item[0], item[1]))
        return [item[2] for item in ranked]

    async def invoke(self, task: TaskSpec, operation: str,
                     payload: dict[str, Any]) -> RoutingOutcome:
        started = time.perf_counter()
        ranked = self.rank(task)
        attempts: list[ProviderAttempt] = []
        for adapter in ranked:
            runtime = self._runtime_for(adapter)
            attempt_started = time.perf_counter()
            try:
                async with runtime.semaphore:
                    output = await asyncio.wait_for(
                        adapter.invoke(operation, payload,
                                       timeout_seconds=task.timeout_seconds),
                        timeout=task.timeout_seconds)
                elapsed = (time.perf_counter() - attempt_started) * 1000
                runtime.circuit.failures = 0
                runtime.circuit.successes += 1
                attempts.append(ProviderAttempt(adapter.name, True, elapsed))
                return RoutingOutcome(output, adapter.name,
                    (time.perf_counter() - started) * 1000,
                    tuple(attempts), len(ranked))
            except Exception as exc:
                elapsed = (time.perf_counter() - attempt_started) * 1000
                runtime.circuit.failures += 1
                if runtime.circuit.failures >= self.circuit_failure_threshold:
                    runtime.circuit.opened_until = time.monotonic() + self.circuit_reset_seconds
                attempts.append(ProviderAttempt(
                    adapter.name, False, elapsed, f"{type(exc).__name__}: {exc}"))
        raise RoutingError(tuple(attempts))

    def health(self) -> dict[str, dict[str, Any]]:
        now = time.monotonic()
        result = {}
        for name, adapter in self.registry._adapters.items():
            runtime = self._runtime_for(adapter)
            result[name] = {
                "available": bool(adapter.healthy),
                "circuit": "open" if runtime.circuit.opened_until > now else "closed",
                "consecutive_failures": runtime.circuit.failures,
                "successes": runtime.circuit.successes,
            }
        return result

    def _runtime_for(self, adapter: Any) -> _ProviderRuntime:
        if adapter.name not in self._runtime:
            profile = self._profile(adapter)
            limit = int(profile.get("max_concurrency",
                                    self.default_provider_concurrency))
            if limit < 1:
                limit = self.default_provider_concurrency
            self._runtime[adapter.name] = _ProviderRuntime(asyncio.Semaphore(limit))
        return self._runtime[adapter.name]

    @staticmethod
    def _profile(adapter: Any) -> Mapping[str, Any]:
        profile = getattr(adapter, "routing_profile", {})
        return profile if isinstance(profile, Mapping) else {}

    @staticmethod
    def _score(profile: Mapping[str, Any], task: TaskSpec) -> float:
        quality = float(profile.get("quality", 0.5))
        reliability = float(profile.get("reliability", 0.9))
        latency = max(1.0, float(profile.get("latency_ms", 1000.0)))
        cost = float(profile.get("cost", 0.5))
        if not 0 <= quality <= 1 or not 0 <= reliability <= 1 or not 0 <= cost <= 1:
            raise ValueError("quality, reliability and cost must be between 0 and 1")
        speed = 1.0 / (1.0 + latency / 5000.0)
        if task.kind.value in {"reason", "verify"}:
            weights = (0.48, 0.30, 0.12, 0.10)
        elif task.kind.value == "tool":
            weights = (0.25, 0.35, 0.25, 0.15)
        else:
            weights = (0.38, 0.30, 0.17, 0.15)
        return (quality * weights[0] + reliability * weights[1]
                + speed * weights[2] + (1.0 - cost) * weights[3])
