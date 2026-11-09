"""Central policy gate. Tool adapters must never bypass this layer."""
from dataclasses import dataclass
from pandoria.contracts import RiskLevel, TaskSpec

@dataclass(frozen=True, slots=True)
class PolicyDecision:
    allowed: bool
    reason: str

class PolicyEngine:
    """Conservative default policy; applications can subclass or compose policies."""
    def evaluate(self, task: TaskSpec, *, side_effecting: bool = False,
                 explicitly_authorized: bool = False) -> PolicyDecision:
        if task.risk == RiskLevel.CRITICAL:
            return PolicyDecision(False, "Critical-risk tasks require a separately approved workflow.")
        if side_effecting and not explicitly_authorized:
            return PolicyDecision(False, "Side-effecting action lacks explicit user authorization.")
        if task.timeout_seconds <= 0 or task.timeout_seconds > 300:
            return PolicyDecision(False, "Task timeout must be between 0 and 300 seconds.")
        if task.max_attempts < 1 or task.max_attempts > 3:
            return PolicyDecision(False, "Attempts must be between 1 and 3.")
        return PolicyDecision(True, "Allowed by baseline policy.")
