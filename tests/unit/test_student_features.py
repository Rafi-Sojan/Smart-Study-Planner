from datetime import datetime, timezone

from src.api.student_features import derive_student_feature_vector


def _intake(**overrides):
    values = {
        "primary_goal": "build_consistency",
        "subjects": ["Mathematics"],
        "course_type": "theory",
        "current_term": 3,
        "current_credit_load": 20,
        "previous_cgpa": 7.5,
        "recent_score_percent": 68,
        "attendance_percent": 82,
        "submission_rate_percent": 75,
        "weekly_study_hours": 8,
        "confidence_level": 3,
        "sleep_hours": 7,
        "stress_level": 6,
        "fatigue_level": 4,
        "concentration_level": 7,
    }
    values.update(overrides)
    return values


def test_derivation_maps_compatible_values_without_inventing_lms_activity() -> None:
    features = (
        "course_type",
        "term_number",
        "attendance_pct_mean",
        "assessment_mean_score",
        "assessment_submitted_rate",
        "active_study_minutes",
        "vle_clicks",
        "remaining_effort_hours",
        "mean_available_hours",
    )
    tasks = [
        {
            "estimated_minutes": 120,
            "completed_minutes": 30,
            "difficulty": 4,
        }
    ]
    availability = [
        {
            "start": datetime(2026, 1, 10, 14, tzinfo=timezone.utc),
            "end": datetime(2026, 1, 10, 16, tzinfo=timezone.utc),
        }
    ]

    result = derive_student_feature_vector(
        features,
        _intake(),
        tasks,
        availability,
        cutoff_days=30,
    )

    assert result.values["course_type"] == "theory"
    assert result.values["term_number"] == 3
    assert result.values["attendance_pct_mean"] == 82
    assert result.values["assessment_mean_score"] == 68
    assert result.values["assessment_submitted_rate"] == 0.75
    assert result.values["active_study_minutes"] == 8 * 60 * 30 / 7
    assert result.values["remaining_effort_hours"] == 1.5
    assert result.values["mean_available_hours"] == 2
    assert result.values["vle_clicks"] is None
    assert result.unavailable_feature_count == 1


def test_derivation_reports_limited_oulad_demo_evidence_without_column_names() -> None:
    result = derive_student_feature_vector(
        (
            "assessment_score_mean",
            "studied_credits",
            "vle_clicks",
            "vle_active_days",
            "vle_resources",
            "date_registration",
        ),
        _intake(),
        [],
        [],
        cutoff_days=60,
    )

    assert result.values["assessment_score_mean"] == 68
    assert result.values["studied_credits"] == 20
    assert result.values["vle_clicks"] is None
    assert result.reliability == "limited"
    assert "vle_clicks" not in result.message
    assert "LMS" in result.message
