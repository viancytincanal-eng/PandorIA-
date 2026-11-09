# Multi-Agent Orchestrator

`pandoria.orchestration.AgentOrchestrator` executes a dependency graph of
specialist model tasks. The cognitive kernel now converts each deterministic
reasoning subtask into a `TaskSpec` and sends the graph to this orchestrator.

Tasks in the same dependency wave run concurrently, bounded by a global
orchestration semaphore and provider-local router limits. Each task receives the
original request context, its own objective and input, and outputs from declared
dependencies only. Results retain provider identity, attempt counts, timings,
errors and provider-attempt details.

A failed dependency blocks its descendants; independent branches continue.
The kernel collects successful terminal outputs into the response and marks the
overall response degraded if any specialist task failed or was skipped.

The executor supports model, reasoning, retrieval and verification adapter
operations. It intentionally rejects `TaskKind.TOOL`: side-effecting tools must
use explicit policy checks, approval and idempotency-aware execution, not generic
model failover. Research subtasks that require `web.search` run only when an
adapter explicitly declares both `web.search` and `text.generate`.

The initial specialist roles are expressed through task kind and role-specific
instructions. They are not separate trained agents by default. Distinct providers
can form a heterogeneous team when the registry has multiple compatible adapters
with meaningful capability declarations and measured routing profiles.

This is orchestration infrastructure, not proof of autonomous specialist quality.
The current verifier performs structural checks only; factual verification,
cross-model critique and evidence scoring remain future layers.
