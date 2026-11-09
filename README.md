# PandorIA

PandorIA is a modular cognitive runtime designed to coordinate models, tools, memory and external integrations through a governed execution pipeline.

## Design principles
- **Model-agnostic core:** providers are adapters, never the brain itself.
- **Layered cognition:** intake, planning, capability routing, execution, verification and reflection are separate stages.
- **Bounded concurrency:** independent tasks can run in parallel under explicit limits and deadlines.
- **Fail-closed integrations:** tools declare capabilities and policies; unavailable or unauthorized tools are not invoked.
- **Memory by interface:** short-term, episodic and semantic stores can be implemented independently.
- **Observable decisions:** each run returns a trace with stages, timings, errors and verification status.

## Architecture
```text
Request -> CognitiveKernel
  -> Intake / Context retrieval
  -> Policy & risk gate
  -> Dependency planner
  -> Capability router
  -> Bounded async scheduler
  -> Model / tool / memory adapters
  -> Evidence-aware verifier
  -> Response + execution trace
```

## Layered reasoning engine

The `pandoria.reasoning` package builds an auditable plan before model execution. It normalizes requests, classifies coarse intent, estimates complexity, extracts explicit constraints, decomposes multi-step work into dependency-linked subtasks, and selects an execution strategy. The kernel includes this plan in the model adapter payload and records its key decisions in the execution trace.

These initial stages are deterministic routing aids, not a substitute for semantic reasoning. A configured model adapter is still required for actual language understanding and generation. See [Reasoning Architecture](docs/REASONING_ARCHITECTURE.md).

## Multi-agent orchestration

The `pandoria.orchestration` layer executes specialist model tasks as a
dependency graph. Independent agents run concurrently under a global limit;
dependent agents receive only the outputs they declared as dependencies.
The kernel then performs a separate synthesis pass and records agent/provider
attempts in its execution trace. Research subtasks require an adapter that
declares `web.search`; missing specialist capabilities are reported rather
than silently simulated. Side-effecting tool tasks are intentionally excluded
from this executor until a separately governed tool runtime is implemented.
See [Multi-Agent Orchestration](docs/MULTI_AGENT_ORCHESTRATION.md).

## Quick start
Requires Python 3.11+.
```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

The first release establishes deterministic engine contracts. It does not pretend to reason intelligently without a configured model adapter. Connect providers through `pandoria/integrations/`.

## Safety and performance
- Configure per-provider and global concurrency limits.
- Give every task a deadline and bounded retry policy.
- Keep credentials in environment variables or a secret manager, never in Git.
- Treat tool output and retrieved documents as untrusted data.
- Require explicit policy approval for side-effecting tools.
- Store only data covered by the configured memory policy.

## Roadmap
1. Core cognitive runtime and test suite.
2. Model adapter registry and provider health/fallback.
3. Persistent memory with Postgres and vector retrieval.
4. Tool permissioning, integration packs and MCP bridge.
5. Evaluation harness, telemetry and adaptive routing.
6. API and user-facing interface.
