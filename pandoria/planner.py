"""Dependency-aware planning and cycle detection."""
from pandoria.contracts import TaskSpec

class PlanningError(ValueError):
    pass

class DependencyPlanner:
    def order(self, tasks: list[TaskSpec]) -> list[list[TaskSpec]]:
        by_id = {task.task_id: task for task in tasks}
        if len(by_id) != len(tasks):
            raise PlanningError("Task identifiers must be unique.")
        for task in tasks:
            missing = set(task.depends_on) - by_id.keys()
            if missing:
                raise PlanningError(f"{task.task_id} depends on unknown tasks: {sorted(missing)}")
        remaining, completed, waves = set(by_id), set(), []
        while remaining:
            ready = sorted(task_id for task_id in remaining
                           if set(by_id[task_id].depends_on) <= completed)
            if not ready:
                raise PlanningError("Task dependency graph contains a cycle.")
            waves.append([by_id[task_id] for task_id in ready])
            completed.update(ready)
            remaining.difference_update(ready)
        return waves
