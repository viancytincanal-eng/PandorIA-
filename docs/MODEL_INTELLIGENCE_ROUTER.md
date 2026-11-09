# Model Intelligence Router

The router selects compatible adapters using task-aware scoring, then performs
bounded failover when a provider errors or times out.

Adapters may expose an optional routing_profile mapping:
- quality: estimated task quality, 0..1
- reliability: estimated reliability, 0..1
- latency_ms: expected latency
- cost: normalized relative cost, 0..1
- max_concurrency: provider-local in-flight request limit

Missing values use conservative defaults. Ranking weights vary by task kind.
A preferred provider receives a modest bonus but must still satisfy capabilities.

Each provider has an independent concurrency semaphore and circuit breaker.
Repeated failures temporarily exclude a provider; a successful call resets its
consecutive failure count. All attempts are recorded in the routing outcome.

Profile values are estimates until an evaluation harness measures them. Circuit
state and metrics are currently process-local, not persistent. Side-effecting tool
operations must not be blindly retried; they need idempotency keys or a separate
retry policy before being routed through this mechanism.

After three or more attempts, observed success ratio is blended into the
reliability score. Provider latency is tracked with an exponentially weighted
moving average and gradually replaces the initial latency estimate. The health
snapshot exposes these process-local measurements for monitoring and later
evaluation-harness integration.
