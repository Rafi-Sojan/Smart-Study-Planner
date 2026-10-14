"""Enrollment-level feature construction for the OULAD baseline."""

import pandas as pd

from src.data.cleaner import clean_oulad_tables


def _assessment_features(
    student_assessment: pd.DataFrame,
    assessments: pd.DataFrame,
) -> pd.DataFrame:
    assessment_map = assessments[
        ["id_assessment", "code_module", "code_presentation"]
    ].drop_duplicates("id_assessment")
    joined = student_assessment.merge(assessment_map, on="id_assessment", how="inner")
    if joined.empty:
        return pd.DataFrame(
            columns=["id_student", "code_presentation", "assessment_count"]
        )
    grouped = joined.groupby(
        ["id_student", "code_module", "code_presentation"],
        as_index=False,
    )
    result = grouped.agg(
        assessment_count=("id_assessment", "nunique"),
        assessment_score_mean=("score", "mean"),
        assessment_score_std=("score", "std"),
        assessment_score_min=("score", "min"),
        assessment_score_max=("score", "max"),
        assessment_score_missing=("score", lambda values: values.isna().sum()),
    )
    return result


def _registration_features(registration: pd.DataFrame) -> pd.DataFrame:
    columns = ["id_student", "code_presentation"]
    available = [column for column in ("date_registration", "date_unregistration") if column in registration]
    if not available:
        return registration[columns].drop_duplicates()
    return registration.groupby(columns, as_index=False)[available].mean()


def _activity_features(
    student_vle: pd.DataFrame,
    vle: pd.DataFrame,
) -> pd.DataFrame:
    if {"code_module", "code_presentation"}.issubset(student_vle.columns):
        joined = student_vle
    else:
        site_map = vle[["id_site", "code_module", "code_presentation"]].drop_duplicates("id_site")
        joined = student_vle.merge(site_map, on="id_site", how="inner")
    if joined.empty:
        return pd.DataFrame(columns=["id_student", "code_presentation", "vle_clicks"])
    return joined.groupby(
        ["id_student", "code_module", "code_presentation"],
        as_index=False,
    ).agg(
        vle_clicks=("sum_click", "sum"),
        vle_active_days=("date", "nunique"),
        vle_resources=("id_site", "nunique"),
    )


def build_oulad_features(
    tables: dict[str, pd.DataFrame],
    clean: bool = True,
) -> pd.DataFrame:
    """Build one labeled row per student-course presentation enrollment.

    ``target_risk`` is 1 for Fail/Withdrawn and 0 for Pass/Distinction. The
    final result is retained as metadata but is excluded by the model helper.
    VLE clicks are activity counts, not study-duration measurements.
    """

    cleaned = clean_oulad_tables(tables) if clean else tables
    info = cleaned["studentInfo"].copy()
    info = info.dropna(subset=["id_student", "code_presentation", "final_result"])
    info["target_risk"] = info["final_result"].isin(["Fail", "Withdrawn"]).astype(int)

    key = ["id_student", "code_presentation"]
    if "studentAssessment" in cleaned and "assessments" in cleaned:
        scores = _assessment_features(cleaned["studentAssessment"], cleaned["assessments"])
        info = info.merge(scores, on=key + ["code_module"], how="left")

    if "studentRegistration" in cleaned:
        registration = _registration_features(cleaned["studentRegistration"])
        info = info.merge(registration, on=key, how="left")

    if "studentVle" in cleaned and "vle" in cleaned:
        activity = _activity_features(cleaned["studentVle"], cleaned["vle"])
        info = info.merge(activity, on=key + ["code_module"], how="left")

    return info.reset_index(drop=True)
