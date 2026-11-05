"""Deterministic, capacity-constrained study-session scheduling."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Iterable

from src.planner.prioritizer import RankedTask


@dataclass(frozen=True)
class AvailabilityWindow:
    start: datetime
    end: datetime


@dataclass(frozen=True)
class PlannedSession:
    task_id: str
    title: str
    subject: str
    start: datetime
    end: datetime
    study_minutes: int
    priority_score: float


def _validated_windows(windows: Iterable[AvailabilityWindow]) -> list[AvailabilityWindow]:
    ordered = sorted(windows, key=lambda value: (value.start, value.end))
    previous_end: datetime | None = None
    for window in ordered:
        if window.end <= window.start:
            raise ValueError("Every availability window must end after it starts")
        if previous_end is not None and window.start < previous_end:
            raise ValueError("Availability windows must not overlap")
        previous_end = window.end
    return ordered


def schedule_ranked_tasks(
    ranked_tasks: Iterable[RankedTask],
    availability: Iterable[AvailabilityWindow],
    *,
    session_minutes: int = 50,
    break_minutes: int = 10,
    minimum_session_minutes: int = 15,
) -> tuple[list[PlannedSession], dict[str, int]]:
    """Allocate non-overlapping sessions and report all unallocated work."""

    if session_minutes < minimum_session_minutes:
        raise ValueError("session_minutes must be at least minimum_session_minutes")
    if break_minutes < 0:
        raise ValueError("break_minutes cannot be negative")
    queue = list(ranked_tasks)
    remaining = {item.task.task_id: item.task.remaining_minutes for item in queue}
    sessions: list[PlannedSession] = []
    windows = _validated_windows(availability)
    queue_position = 0

    for window in windows:
        cursor = window.start
        while queue and cursor < window.end:
            active = [item for item in queue if remaining[item.task.task_id] > 0]
            if not active:
                break
            item = active[queue_position % len(active)]
            queue_position += 1
            available_minutes = int((window.end - cursor).total_seconds() // 60)
            study_minutes = min(
                session_minutes,
                remaining[item.task.task_id],
                available_minutes,
            )
            if study_minutes < minimum_session_minutes:
                break
            end = cursor + timedelta(minutes=study_minutes)
            sessions.append(
                PlannedSession(
                    task_id=item.task.task_id,
                    title=item.task.title,
                    subject=item.task.subject,
                    start=cursor,
                    end=end,
                    study_minutes=study_minutes,
                    priority_score=item.priority_score,
                )
            )
            remaining[item.task.task_id] -= study_minutes
            cursor = end + timedelta(minutes=break_minutes)

    return sessions, {
        task_id: int(minutes)
        for task_id, minutes in remaining.items()
        if minutes > 0
    }
