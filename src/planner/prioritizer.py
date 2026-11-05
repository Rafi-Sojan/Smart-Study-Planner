"""Transparent, deterministic study-task prioritization.

The model risk score is used as a modest global support signal.  It never
changes deadlines, removes tasks, or makes punitive academic decisions.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable


@dataclass(frozen=True)
class PlanningTask:
    task_id: str
    title: str
    subject: str
    deadline: datetime
    estimated_minutes: int
    completed_minutes: int = 0
    difficulty: int = 3
    importance: int = 3

    @property
    def remaining_minutes(self) -> int:
        return max(0, self.estimated_minutes - self.completed_minutes)


@dataclass(frozen=True)
class RankedTask:
    task: PlanningTask
    priority_score: float
    rationale: tuple[str, ...]


def rank_tasks(
    tasks: Iterable[PlanningTask],
    risk_score: float,
    planning_time: datetime,
    risk_threshold: float = 0.5,
) -> list[RankedTask]:
    """Rank incomplete work using documented urgency and workload factors."""

    if not 0 <= risk_score <= 1:
        raise ValueError("risk_score must be between zero and one")
    if not 0 < risk_threshold < 1:
        raise ValueError("risk_threshold must be strictly between zero and one")
    ranked: list[RankedTask] = []
    for task in tasks:
        if task.remaining_minutes <= 0:
            continue
        hours_to_deadline = (task.deadline - planning_time).total_seconds() / 3600.0
        days_to_deadline = hours_to_deadline / 24.0
        urgency = 1.0 if days_to_deadline <= 0 else max(0.0, 1.0 - days_to_deadline / 30.0)
        available_days = max(days_to_deadline, 1.0)
        workload_pressure = min(1.0, task.remaining_minutes / (available_days * 120.0))
        importance = task.importance / 5.0
        difficulty = task.difficulty / 5.0
        score = (
            0.35 * urgency
            + 0.25 * importance
            + 0.15 * difficulty
            + 0.15 * workload_pressure
            + 0.10 * risk_score
        )
        rationale = [
            f"{task.remaining_minutes} minutes remain",
            (
                "deadline has passed"
                if days_to_deadline <= 0
                else f"deadline is in {days_to_deadline:.1f} days"
            ),
            f"importance {task.importance}/5 and difficulty {task.difficulty}/5",
        ]
        if risk_score >= risk_threshold:
            rationale.append("elevated course-risk signal supports earlier structured study")
        ranked.append(
            RankedTask(
                task=task,
                priority_score=round(float(score), 6),
                rationale=tuple(rationale),
            )
        )
    return sorted(
        ranked,
        key=lambda value: (
            -value.priority_score,
            value.task.deadline,
            value.task.task_id,
        ),
    )
