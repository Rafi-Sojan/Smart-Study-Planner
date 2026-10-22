"""Build the shared engagement contract for synthetic transfer testing."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


TRANSFER_FEATURE_COLUMNS = (
    "course_id",
    "activity_count",
    "active_day_count",
    "content_count",
    "session_count",
    "mean_daily_activity",
    "has_activity",
)


def build_synthetic_transfer_features(
    data_dir: str | Path,
    cutoff_days: int = 60,
) -> pd.DataFrame:
    """Build synthetic enrollment rows with comparable engagement features.

    The synthetic release does not have the same LMS action log as KU Leuven.
    Study-session records are therefore used as the observable engagement
    event: session rows provide activity/session counts, dates provide active
    days, and topics provide a content proxy. Planner-only wellbeing and
    recommendation fields are intentionally excluded.
    """

    if cutoff_days < 0:
        raise ValueError("cutoff_days must be non-negative")
    root = Path(data_dir)
    enrollments = pd.read_csv(root / "enrollments.csv")
    offerings = pd.read_csv(root / "course_offerings.csv", usecols=["offering_id", "course_id", "term_id"])
    terms = pd.read_csv(root / "academic_terms.csv", usecols=["term_id", "start_date"])
    outcomes = pd.read_csv(root / "outcomes.csv", usecols=["student_id", "offering_id", "passed"])
    sessions = pd.read_csv(
        root / "study_sessions.csv",
        usecols=["session_id", "student_id", "enrollment_id", "topic_id", "planned_start"],
    )

    terms["start_date"] = pd.to_datetime(terms["start_date"], errors="raise")
    base = (
        enrollments.merge(offerings, on="offering_id", how="left", validate="many_to_one")
        .merge(terms, on="term_id", how="left", validate="many_to_one")
        .merge(outcomes, on=["student_id", "offering_id"], how="left", validate="one_to_one")
    )
    if base["passed"].isna().any():
        raise ValueError("Synthetic transfer features require an outcome for every enrollment")
    base["target_risk"] = (~base["passed"].astype(bool)).astype(int)
    base["cutoff_date"] = base["start_date"] + pd.to_timedelta(cutoff_days, unit="D")

    sessions["planned_start"] = pd.to_datetime(sessions["planned_start"], errors="raise")
    sessions = sessions.merge(
        base[["enrollment_id", "start_date", "cutoff_date"]],
        on="enrollment_id",
        how="inner",
        validate="many_to_one",
    )
    sessions = sessions.loc[
        sessions["planned_start"].between(sessions["start_date"], sessions["cutoff_date"], inclusive="both")
    ].copy()
    if sessions.empty:
        summary = pd.DataFrame(columns=["enrollment_id", *TRANSFER_FEATURE_COLUMNS[1:]])
    else:
        summary = (
            sessions.groupby("enrollment_id", dropna=False)
            .agg(
                activity_count=("session_id", "size"),
                active_day_count=("planned_start", lambda values: values.dt.normalize().nunique()),
                content_count=("topic_id", "nunique"),
                session_count=("session_id", "nunique"),
            )
            .reset_index()
        )
        summary["mean_daily_activity"] = summary["activity_count"] / summary["active_day_count"]

    result = base.merge(summary, on="enrollment_id", how="left", validate="one_to_one")
    count_columns = [
        "activity_count",
        "active_day_count",
        "content_count",
        "session_count",
        "mean_daily_activity",
    ]
    for column in count_columns:
        result[column] = result[column].fillna(0)
    result["has_activity"] = (result["activity_count"] > 0).astype(int)
    return result
