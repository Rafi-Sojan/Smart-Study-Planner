from datetime import datetime, timedelta, timezone

from src.planner.prioritizer import PlanningTask, rank_tasks
from src.planner.recommendations import build_recommendations
from src.planner.scheduler import AvailabilityWindow, schedule_ranked_tasks


def _time(hour: int) -> datetime:
    return datetime(2026, 1, 10, hour, tzinfo=timezone.utc)


def test_priority_ranking_is_deterministic_and_deadline_aware() -> None:
    tasks = [
        PlanningTask("later", "Later work", "Math", _time(12) + timedelta(days=20), 120),
        PlanningTask("urgent", "Urgent work", "Physics", _time(12) + timedelta(days=1), 120),
    ]

    ranked = rank_tasks(tasks, risk_score=0.6, planning_time=_time(12))

    assert [item.task.task_id for item in ranked] == ["urgent", "later"]
    assert "deadline is in 1.0 days" in ranked[0].rationale


def test_scheduler_respects_capacity_breaks_and_reports_shortfall() -> None:
    ranked = rank_tasks(
        [PlanningTask("task-1", "Assignment", "Math", _time(12) + timedelta(days=2), 120)],
        risk_score=0.5,
        planning_time=_time(12),
    )
    sessions, unscheduled = schedule_ranked_tasks(
        ranked,
        [AvailabilityWindow(_time(14), _time(16))],
        session_minutes=50,
        break_minutes=10,
    )

    assert [session.study_minutes for session in sessions] == [50, 50]
    assert sessions[1].start - sessions[0].end == timedelta(minutes=10)
    assert unscheduled == {"task-1": 20}


def test_scheduler_rejects_overlapping_availability() -> None:
    ranked = rank_tasks(
        [PlanningTask("task-1", "Assignment", "Math", _time(12) + timedelta(days=2), 60)],
        risk_score=0.2,
        planning_time=_time(12),
    )
    windows = [
        AvailabilityWindow(_time(14), _time(16)),
        AvailabilityWindow(_time(15), _time(17)),
    ]

    try:
        schedule_ranked_tasks(ranked, windows)
    except ValueError as error:
        assert "must not overlap" in str(error)
    else:  # pragma: no cover - assertion guard
        raise AssertionError("overlapping windows should be rejected")


def test_planner_language_uses_configured_model_threshold() -> None:
    ranked = rank_tasks(
        [PlanningTask("task-1", "Assignment", "Math", _time(12) + timedelta(days=2), 60)],
        risk_score=0.4,
        planning_time=_time(12),
        risk_threshold=0.3,
    )

    assert "elevated course-risk signal" in ranked[0].rationale[-1]
    recommendations = build_recommendations(
        0.4,
        ranked,
        [],
        {},
        risk_threshold=0.3,
    )
    assert recommendations[0].startswith("Review progress with a tutor")
