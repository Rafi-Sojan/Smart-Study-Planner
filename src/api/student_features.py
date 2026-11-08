"""Derive serving features from a small, student-facing demonstration intake.

This adapter does not pretend that self-reported answers are institutional
records. It maps only semantically compatible values, leaves unavailable LMS
features missing for the fitted preprocessing pipeline, and reports evidence
coverage without exposing internal feature names to the student interface.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from math import ceil
from typing import Any, Iterable, Mapping, Sequence


FeatureValue = bool | int | float | str | None


@dataclass(frozen=True)
class StudentFeatureDerivation:
    """One exact model vector plus a student-safe evidence summary."""

    values: dict[str, FeatureValue]
    mapped_feature_count: int
    unavailable_feature_count: int
    coverage_percent: float
    reliability: str
    source_labels: tuple[str, ...]
    message: str


def _optional_number(value: Any) -> float | None:
    if value is None or value == "":
        return None
    return float(value)


def _mean_available_hours(availability: Sequence[Mapping[str, Any]]) -> float | None:
    total_hours = 0.0
    dates: set[object] = set()
    for slot in availability:
        start = slot.get("start")
        end = slot.get("end")
        if not isinstance(start, datetime) or not isinstance(end, datetime) or end <= start:
            continue
        total_hours += (end - start).total_seconds() / 3600
        dates.add(start.date())
    if not dates:
        return None
    return total_hours / len(dates)


def _task_summary(tasks: Sequence[Mapping[str, Any]]) -> tuple[float | None, str | None]:
    remaining_minutes = 0.0
    difficulties: list[float] = []
    for task in tasks:
        estimated = _optional_number(task.get("estimated_minutes"))
        completed = _optional_number(task.get("completed_minutes")) or 0.0
        if estimated is not None:
            remaining_minutes += max(estimated - completed, 0.0)
        difficulty = _optional_number(task.get("difficulty"))
        if difficulty is not None:
            difficulties.append(difficulty)
    remaining_hours = remaining_minutes / 60 if tasks else None
    if not difficulties:
        return remaining_hours, None
    mean_difficulty = sum(difficulties) / len(difficulties)
    if mean_difficulty < 2.5:
        category = "easy"
    elif mean_difficulty < 3.75:
        category = "medium"
    else:
        category = "hard"
    return remaining_hours, category


def _source_labels(
    intake: Mapping[str, Any],
    tasks: Sequence[Mapping[str, Any]],
    availability: Sequence[Mapping[str, Any]],
) -> tuple[str, ...]:
    labels = ["Study goal and subjects"]
    academic_fields = (
        "previous_cgpa",
        "recent_score_percent",
        "attendance_percent",
        "submission_rate_percent",
        "weekly_study_hours",
        "confidence_level",
        "current_credit_load",
    )
    wellbeing_fields = (
        "sleep_hours",
        "stress_level",
        "fatigue_level",
        "concentration_level",
    )
    if any(intake.get(name) is not None for name in academic_fields):
        labels.append("Self-reported academic snapshot")
    if tasks:
        labels.append("Task workload")
    if availability:
        labels.append("Availability preferences")
    if any(intake.get(name) is not None for name in wellbeing_fields):
        labels.append("Optional wellbeing context")
    return tuple(labels)


def derive_student_feature_vector(
    feature_names: Iterable[str],
    intake: Mapping[str, Any],
    tasks: Sequence[Mapping[str, Any]],
    availability: Sequence[Mapping[str, Any]],
    *,
    cutoff_days: int | None,
) -> StudentFeatureDerivation:
    """Construct the exact fitted contract from understandable demo inputs.

    Values are mapped only when the intake and trained feature have compatible
    meanings. No LMS clicks, verified attendance records, assessment events,
    or historical outcomes are invented.
    """

    names = tuple(str(name) for name in feature_names)
    values: dict[str, FeatureValue] = {name: None for name in names}
    recent_score = _optional_number(intake.get("recent_score_percent"))
    attendance = _optional_number(intake.get("attendance_percent"))
    submission_rate = _optional_number(intake.get("submission_rate_percent"))
    weekly_study_hours = _optional_number(intake.get("weekly_study_hours"))
    previous_cgpa = _optional_number(intake.get("previous_cgpa"))
    confidence = _optional_number(intake.get("confidence_level"))
    sleep_hours = _optional_number(intake.get("sleep_hours"))
    stress = _optional_number(intake.get("stress_level"))
    fatigue = _optional_number(intake.get("fatigue_level"))
    concentration = _optional_number(intake.get("concentration_level"))
    credit_load = _optional_number(intake.get("current_credit_load"))
    mean_available_hours = _mean_available_hours(availability)
    remaining_effort_hours, difficulty = _task_summary(tasks)
    observation_days = max(int(cutoff_days or 30), 1)
    active_study_minutes = (
        weekly_study_hours * 60 * observation_days / 7
        if weekly_study_hours is not None
        else None
    )

    compatible_values: dict[str, FeatureValue] = {
        # Synthetic early-warning contract.
        "course_type": intake.get("course_type"),
        "term_number": intake.get("current_term"),
        "credits": credit_load,
        "difficulty": difficulty,
        "prior_semester_gpa": previous_cgpa,
        "prior_cumulative_gpa": previous_cgpa,
        "attendance_pct_at_cutoff": attendance,
        "attendance_pct_mean": attendance,
        "assessment_mean_score": recent_score,
        "assessment_submitted_rate": (
            submission_rate / 100 if submission_rate is not None else None
        ),
        "active_study_minutes": active_study_minutes,
        "mean_confidence_score": confidence / 5 if confidence is not None else None,
        "remaining_effort_hours": remaining_effort_hours,
        "mean_sleep_hours": sleep_hours,
        "mean_sleep_deficit_hours": (
            max(8.0 - sleep_hours, 0.0) if sleep_hours is not None else None
        ),
        "mean_fatigue_score": fatigue,
        "mean_topic_fatigue": fatigue,
        "mean_concentration_score": concentration,
        "mean_stress_score": stress,
        "mean_available_hours": mean_available_hours,
        # OULAD contracts use a different name for the compatible assessment
        # aggregate and course-load context.
        "assessment_score_mean": recent_score,
        "studied_credits": credit_load,
    }
    for name in names:
        if name in compatible_values:
            values[name] = compatible_values[name]

    mapped_count = sum(value is not None for value in values.values())
    unavailable_count = len(values) - mapped_count
    coverage = round((mapped_count / len(values) * 100) if values else 0.0, 1)
    minimum_partial = max(3, ceil(len(values) * 0.25))
    reliability = "partial" if mapped_count >= minimum_partial else "limited"
    message = (
        "This demonstration uses self-reported academic context and planning inputs. "
        "Verified LMS attendance, assessment, and engagement records are not connected, "
        "so the support signal is provisional."
    )
    return StudentFeatureDerivation(
        values=values,
        mapped_feature_count=mapped_count,
        unavailable_feature_count=unavailable_count,
        coverage_percent=coverage,
        reliability=reliability,
        source_labels=_source_labels(intake, tasks, availability),
        message=message,
    )
