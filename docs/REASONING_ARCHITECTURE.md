# PandorIA Reasoning Architecture

## Purpose
The reasoning engine is the control structure around intelligence providers. It creates an explicit, inspectable plan; it is not itself a language model and does not pretend deterministic heuristics are deep reasoning.

## Pipeline
1. **Normalization**: validates and canonicalizes the request.
2. **Intent analysis**: assigns a coarse task family (research, build, plan, explain, creative, general).
3. **Complexity estimation**: selects a lightweight or multi-stage plan.
4. **Constraint extraction**: preserves explicit exclusions, limits and deadlines.
5. **Task decomposition**: creates dependency-linked subtasks.
6. **Strategy selection**: chooses evidence-first, build-verify, progressive explanation, or analyze-solve-review.
7. **Model execution**: future provider adapters perform semantic analysis and generation.
8. **Verification**: independent evaluators inspect output and evidence before delivery.

## Extension contracts
Add a stage by implementing a pure function over typed context or a protocol-backed component. Keep providers outside the reasoning package. A provider must declare capabilities, health, timeout behavior and its own concurrency budget.

## Performance rules
- Default stages are synchronous, deterministic and dependency-free.
- Do not fan out subtasks unless their dependency graph permits it.
- Apply global and per-provider concurrency limits.
- Bound request size, task count, retries and deadlines.
- Cache only stable, non-sensitive intermediate results with explicit invalidation.
- Emit stage timing and failure metadata without logging prompts or secrets by default.

## Current limitations
Intent classification and constraint extraction are heuristic baselines. They are routing aids, not authoritative semantic judgments. Actual multi-step reasoning requires a configured model adapter and independent evaluation.
