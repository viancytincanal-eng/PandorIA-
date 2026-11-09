import pytest
from pandoria.contracts import TaskSpec
from pandoria.planner import DependencyPlanner, PlanningError

def test_planner_groups_independent_tasks_and_respects_dependencies():
    tasks = [TaskSpec("a", "A"), TaskSpec("b", "B"),
             TaskSpec("c", "C", depends_on=("a", "b"))]
    waves = DependencyPlanner().order(tasks)
    assert [[task.task_id for task in wave] for wave in waves] == [["a", "b"], ["c"]]

def test_planner_rejects_cycles():
    tasks = [TaskSpec("a", "A", depends_on=("b",)),
             TaskSpec("b", "B", depends_on=("a",))]
    with pytest.raises(PlanningError):
        DependencyPlanner().order(tasks)

def test_planner_rejects_missing_dependencies():
    with pytest.raises(PlanningError):
        DependencyPlanner().order([TaskSpec("a", "A", depends_on=("missing",))])
