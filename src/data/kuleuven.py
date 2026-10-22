"""Load and build leakage-aware features from the KU Leuven dataset.

The public KU Leuven release contains course-participation outcome tables and
LMS activity logs for three academic years.  This adapter deliberately uses
only activity observed by a course-relative cutoff.  Final score categories
and the final ``PASSED`` field are retained only as the binary evaluation
target; they are never passed to the predictor matrix.
"""

from __future__ import annotations

from pathlib import Path
from zipfile import ZipFile

import pandas as pd


PRESENTATIONS = ("1819", "1920", "2021")
PARTICIPATION_TEMPLATE = "dataset/{year}_course_participation.xlsx"
ACTIVITY_TEMPLATE = "dataset/{year}_log_activity.csv"


def _member_path(data_path: str | Path, member: str) -> tuple[Path | None, str | None]:
    """Resolve a member from an extracted directory or a ZIP archive."""

    root = Path(data_path)
    if root.is_file() and root.suffix.lower() == ".zip":
        return None, member
    candidates = [root / member, root / Path(member).name]
    for candidate in candidates:
        if candidate.exists():
            return candidate, None
    raise FileNotFoundError(f"KU Leuven dataset member not found: {member}")


def _read_excel(data_path: str | Path, member: str) -> pd.DataFrame:
    path, archive_member = _member_path(data_path, member)
    if archive_member is not None:
        with ZipFile(Path(data_path)) as archive, archive.open(archive_member) as stream:
            return pd.read_excel(stream, engine="openpyxl")
    return pd.read_excel(path, engine="openpyxl")


def _read_csv(data_path: str | Path, member: str) -> pd.DataFrame:
    path, archive_member = _member_path(data_path, member)
    usecols = ["ACTION_ID", "COURSE_ID", "USER_ID", "CONTENT_ID", "SESSION_ID", "TIMESTAMP"]
    dtype = {
        "COURSE_ID": "string",
        "USER_ID": "Int64",
        "CONTENT_ID": "Int64",
        "SESSION_ID": "Int64",
    }
    if archive_member is not None:
        with ZipFile(Path(data_path)) as archive, archive.open(archive_member) as stream:
            return pd.read_csv(stream, usecols=usecols, dtype=dtype, parse_dates=["TIMESTAMP"])
    return pd.read_csv(path, usecols=usecols, dtype=dtype, parse_dates=["TIMESTAMP"])


def load_kuleuven_participation(data_path: str | Path) -> pd.DataFrame:
    """Load all participation outcomes and normalise them to project names."""

    frames: list[pd.DataFrame] = []
    for presentation in PRESENTATIONS:
        frame = _read_excel(data_path, PARTICIPATION_TEMPLATE.format(year=presentation))
        frame.columns = frame.columns.astype(str).str.strip().str.lower()
        required = {"course_id", "user_id", "passed"}
        missing = required.difference(frame.columns)
        if missing:
            raise ValueError(f"{presentation} participation table is missing: {sorted(missing)}")
        frame = frame.rename(columns={"user_id": "id_student"})
        frame["id_student"] = pd.to_numeric(frame["id_student"], errors="raise").astype("int64")
        frame["course_id"] = frame["course_id"].astype("string")
        frame["code_presentation"] = presentation
        frame["id_presentation"] = presentation + "_" + frame["course_id"].astype(str)
        frame["target_risk"] = 1 - pd.to_numeric(frame["passed"], errors="raise").astype(int)
        frames.append(frame)
    result = pd.concat(frames, ignore_index=True)
    duplicate_keys = ["code_presentation", "id_student", "course_id"]
    conflicting = (
        result.groupby(duplicate_keys, dropna=False)["target_risk"].nunique().gt(1).any()
    )
    if conflicting:
        raise ValueError("KU Leuven has conflicting outcomes for a repeated participation key")
    result = result.drop_duplicates(subset=duplicate_keys, keep="first").reset_index(drop=True)
    if result["target_risk"].nunique() != 2:
        raise ValueError("KU Leuven outcomes must contain both risk classes")
    return result


def _activity_summary(events: pd.DataFrame, cutoff_days: int) -> pd.DataFrame:
    """Aggregate only activity observed between day zero and a cutoff."""

    observed = events.loc[
        events["days_since_course_anchor"].between(0, cutoff_days, inclusive="both")
    ].copy()
    keys = ["id_student", "course_id"]
    if observed.empty:
        return pd.DataFrame(columns=keys + [
            "activity_count",
            "active_day_count",
            "content_count",
            "session_count",
        ])
    summary = (
        observed.groupby(keys, dropna=False)
        .agg(
            activity_count=("ACTION_ID", "size"),
            active_day_count=("days_since_course_anchor", "nunique"),
            content_count=("CONTENT_ID", "nunique"),
            session_count=("SESSION_ID", "nunique"),
        )
        .reset_index()
    )
    summary["mean_daily_activity"] = summary["activity_count"] / summary["active_day_count"]
    return summary


def build_kuleuven_features(
    data_path: str | Path,
    cutoff_days: int = 60,
) -> pd.DataFrame:
    """Build one participation-level feature frame for a cutoff.

    The release does not provide a single canonical course-start column.  The
    first recorded activity for each course and academic year is therefore
    used as the observation anchor, and that assumption is recorded in the
    external-validation documentation.
    """

    if cutoff_days < 0:
        raise ValueError("cutoff_days must be non-negative")
    participation = load_kuleuven_participation(data_path)
    feature_frames: list[pd.DataFrame] = []
    for presentation in PRESENTATIONS:
        base = participation.loc[participation["code_presentation"].eq(presentation)].copy()
        events = _read_csv(data_path, ACTIVITY_TEMPLATE.format(year=presentation))
        events["course_id"] = events["COURSE_ID"].astype("string")
        events["id_student"] = events["USER_ID"].astype("Int64")
        anchors = events.groupby("course_id")["TIMESTAMP"].min()
        events["course_start_anchor"] = events["course_id"].map(anchors)
        events["days_since_course_anchor"] = (
            events["TIMESTAMP"] - events["course_start_anchor"]
        ).dt.days
        summary = _activity_summary(events, cutoff_days)
        merged = base.merge(summary, on=["id_student", "course_id"], how="left", validate="one_to_one")
        count_columns = [
            "activity_count",
            "active_day_count",
            "content_count",
            "session_count",
            "mean_daily_activity",
        ]
        for column in count_columns:
            merged[column] = merged[column].fillna(0)
        merged["has_activity"] = (merged["activity_count"] > 0).astype(int)
        merged["course_start_anchor"] = merged["course_id"].map(anchors)
        feature_frames.append(merged)

    result = pd.concat(feature_frames, ignore_index=True)
    result["observation_cutoff_days"] = cutoff_days
    return result


def build_kuleuven_cutoff_features(
    data_path: str | Path,
    cutoffs_days: tuple[int, ...] = (30, 60, 90),
) -> dict[int, pd.DataFrame]:
    """Build separate leakage-aware frames for all requested cutoffs."""

    cutoffs = tuple(sorted({int(value) for value in cutoffs_days}))
    if not cutoffs or any(value < 0 for value in cutoffs):
        raise ValueError("cutoffs_days must contain non-negative integers")
    return {cutoff: build_kuleuven_features(data_path, cutoff) for cutoff in cutoffs}
