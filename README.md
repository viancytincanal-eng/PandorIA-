# PandorIA

PandorIA is a modular cognitive runtime designed to coordinate models, tools, memory and external integrations through a governed execution pipeline.

## Design principles
- **Model-agnostic core:** providers are adapters, never the brain itself.
- **Layered cognition:** intake, planning, capability routing, execution, verification and reflection are separate stages.
- **Specialist orchestration:** independent subtasks run concurrently; dependent tasks wait for upstream results.
- **Bounded concurrency:** independent tasks run in parallel under explicit limits and deadlines.
- **Fail-closed integrations:** tools declare capabilities and policies; unavailable or unauthorized tools are not invoked.
- **Memory by interface:** short-term, episodic and semantic stores can be implemented independently.
- **Observable decisions:** each run returns a trace with stages, timings, errors and verification status.

## Architecture
```text
Request -> CognitiveKernel
  -> Intake / Context retrieval
  -> Policy & risk gate
  -> Layered reasoning plan
  -> Dependency graph / specialist orchestration
  -> Capability-aware model router
  -> Bounded parallel execution / failover
  -> Model, tool and memory adapters
  -> Verification
  -> Response + execution trace
```

## Layered reasoning engine

The `pandoria.reasoning` package normalizes requests, classifies coarse intent, estimates complexity, extracts explicit constraints, decomposes multi-step work into dependency-linked subtasks and selects an execution strategy. See [Reasoning Architecture](docs/REASONING_ARCHITECTURE.md).

These deterministic stages organize work; they are not a substitute for semantic reasoning.

## Model intelligence router

The `pandoria.model_intelligence` package ranks capability-compatible providers using routing profiles and observed performance. It provides per-provider concurrency limits, failover, circuit breakers and health metrics. See [Model Intelligence Router](docs/MODEL_INTELLIGENCE_ROUTER.md).

## Multi-agent orchestration

The `pandoria.orchestration` package turns reasoning subtasks into role-specialized model calls. Independent branches execute concurrently, dependency outputs flow into later stages, and failed branches prevent dependent work from running. The initial specialist roles are prompt profiles, not separate trained agents unless different providers are configured. See [Multi-Agent Orchestration](docs/MULTI_AGENT_ORCHESTRATION.md).

## Quick start
Requires Python 3.11+.
```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

The runtime requires at least one registered adapter with `text.generate` for model execution. Tasks that require additional capabilities, such as `web.search`, run only when an adapter declares those capabilities.

## Safety and performance
- Configure per-provider and global concurrency limits.
- Give every task a deadline and bounded retry policy.
- Keep credentials in environment variables or a secret manager, never in Git.
- Treat tool output and retrieved documents as untrusted data.
- Require explicit policy approval for side-effecting tools.
- Store only data covered by the configured memory policy.
- Do not treat structural verification as proof of factual correctness.

## Roadmap
1. Core cognitive runtime and test suite.
2. Model adapter registry, intelligent routing and provider resilience.
3. Multi-agent orchestration and evaluation.
4. Persistent memory with Postgres and vector retrieval.
5. Tool permissioning, integration packs and MCP bridge.
6. Evaluation harness, telemetry and adaptive routing.
7. API and user-facing interface.
