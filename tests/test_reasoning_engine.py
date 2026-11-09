from pytest import raises
from pandoria.reasoning import ReasoningEngine


def test_build_request_gets_ordered_multistage_plan():
    plan = ReasoningEngine().plan(
        "Construye e implementa una API modular y después verifica sus pruebas."
    )
    assert plan.context.intent == "build"
    assert [task.id for task in plan.subtasks] == [
        "specify", "design", "implement", "verify"
    ]
    assert plan.subtasks[-1].depends_on == ("implement",)


def test_research_plan_marks_external_evidence():
    plan = ReasoningEngine().plan("Investiga y compara fuentes recientes sobre agentes.")
    assert plan.requires_external_evidence is True
    assert plan.strategy == "evidence_first"


def test_empty_or_oversized_request_is_rejected():
    engine = ReasoningEngine(max_request_chars=5)
    with raises(ValueError):
        engine.plan(" ")
    with raises(ValueError):
        engine.plan("demasiado largo")
