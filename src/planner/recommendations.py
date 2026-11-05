"""Human-readable, non-punitive recommendations for a generated plan."""

from __future__ import annotations

from typing import Iterable

from src.planner.prioritizer import RankedTask
from src.planner.scheduler import PlannedSession


def build_recommendations(
    risk_score: float,
    ranked_tasks: Iterable[RankedTask],
    sessions: Iterable[PlannedSession],
    unscheduled_minutes: dict[str, int],
    risk_threshold: float = 0.5,
) -> list[str]:
    """Explain practical next steps without claiming causal intervention effects."""

    if not 0 < risk_threshold < 1:
        raise ValueError("risk_threshold must be strictly between zero and one")
    ranked = list(ranked_tasks)
    scheduled = list(sessions)
    recommendations: list[str] = []
    high_support_threshold = max(0.7, risk_threshold)
    if risk_score >= high_support_threshold:
        recommendations.append(
            "Arrange a supportive check-in with an academic adviser; the risk score is a screening signal, not a diagnosis."
        )
    elif risk_score >= risk_threshold:
        recommendations.append(
            "Review progress with a tutor and reassess the plan after the next attendance or assessment update."
        )
    else:
        recommendations.append(
            "Continue the planned study routine and review progress when new course evidence becomes available."
        )
    if ranked:
        recommendations.append(
            f"Start with {ranked[0].task.title!r}; it has the highest documented urgency and workload score."
        )
    if unscheduled_minutes:
        recommendations.append(
            "Available time is insufficient for all remaining work; add availability or ask a tutor to review priorities."
        )
    if scheduled:
        recommendations.append(
            "Use the configured breaks between sessions and stop or shorten a session if fatigue increases."
        )
    recommendations.append(
        "A learner or adviser should review deadlines, accessibility needs, and personal constraints before accepting the plan."
    )
    return recommendations
