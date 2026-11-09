# Multi-Agent Orchestrator

`pandoria.orchestration.AgentOrchestrator` executes a dependency graph of
specialist model tasks. Tasks in the same dependency wave run concurrently,
bounded by a global orchestration semaphore and provider-local router limits.

Each agent receives the original request context, its own objective and input,
and outputs from its declared dependencies only. Results retain provider identity,
attempt counts, timings and errors. A failed dependency blocks its descendants;
independent branches continue and remain available for synthesis or diagnosis.

The initial executor supports model, reasoning, retrieval and verification
adapter operations. It intentionally rejects `TaskKind.TOOL`: side-effecting
tools must use explicit policy checks, approval and idempotency-aware execution,
not generic model failover.

This is orchestration infrastructure, not proof of autonomous specialist quality.
The semantic quality of each agent depends on configured adapters and their
measured capabilities. The kernel's integration and evidence-aware synthesis
are subsequent steps.
