from pandoria.contracts import RiskLevel, TaskSpec
from pandoria.policy import PolicyEngine

def test_side_effects_require_explicit_authorization():
    task = TaskSpec("send", "Send a message", risk=RiskLevel.MEDIUM)
    assert not PolicyEngine().evaluate(task, side_effecting=True).allowed
    assert PolicyEngine().evaluate(task, side_effecting=True,
                                   explicitly_authorized=True).allowed

def test_critical_risk_is_blocked_by_baseline_policy():
    task = TaskSpec("critical", "Critical", risk=RiskLevel.CRITICAL)
    assert not PolicyEngine().evaluate(task).allowed
