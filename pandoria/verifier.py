"""Baseline structural verification; factual checks require specialist evaluators."""
from pandoria.contracts import Verification

class ResponseVerifier:
    def verify(self, answer: str, *, task_errors: list[str]) -> Verification:
        issues = list(task_errors)
        if not answer.strip():
            issues.append("The response is empty.")
        confidence = 0.95 if not issues else max(0.15, 0.65 - 0.1 * len(issues))
        return Verification(passed=not issues, confidence=confidence,
                            issues=tuple(issues),
                            evidence=("Baseline structural checks only; factual correctness is not established.",))
