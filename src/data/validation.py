"""Relational and domain checks for supplied OULAD tables.

These checks intentionally validate rather than repair data. A failed check is
an explicit reason to stop a run instead of silently producing a plausible but
incorrect feature table.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from src.data.cleaner import VALID_OUTCOMES


def audit_oulad_tables(tables: dict[str, pd.DataFrame]) -> dict[str, Any]:
    """Return measurable quality findings without modifying the input tables."""

    findings: dict[str, Any] = {"tables": {}, "errors": [], "warnings": []}
    for name, frame in tables.items():
        findings["tables"][name] = {
            "rows": int(len(frame)),
            "columns": int(len(frame.columns)),
            "duplicate_rows": int(frame.duplicated().sum()),
            "missing_cells": int(frame.isna().sum().sum()),
        }

    info = tables.get("studentInfo")
    if info is not None:
        invalid_outcomes = sorted(
            set(info["final_result"].dropna().astype(str)) - VALID_OUTCOMES
        ) if "final_result" in info else []
        if invalid_outcomes:
            findings["errors"].append({"table": "studentInfo", "invalid_final_result": invalid_outcomes})
        enrollment_key = [
            column
            for column in ("id_student", "code_module", "code_presentation")
            if column in info.columns
        ]
        if len(enrollment_key) >= 2:
            duplicates = int(info.duplicated(enrollment_key).sum())
            if duplicates:
                findings["errors"].append(
                    {"table": "studentInfo", "duplicate_enrollment_keys": duplicates}
                )

    assessments = tables.get("assessments")
    if assessments is not None:
        if "id_assessment" in assessments and assessments["id_assessment"].duplicated().any():
            findings["errors"].append({"table": "assessments", "duplicate_assessment_ids": True})
        if "weight" in assessments and (~assessments["weight"].between(0, 100)).any():
            findings["errors"].append({"table": "assessments", "weight_out_of_range": True})

    student_assessment = tables.get("studentAssessment")
    if student_assessment is not None:
        if "score" in student_assessment:
            invalid = student_assessment["score"].notna() & ~student_assessment["score"].between(0, 100)
            if invalid.any():
                findings["errors"].append(
                    {"table": "studentAssessment", "score_out_of_range": int(invalid.sum())}
                )
        if "date_submitted" in student_assessment:
            negative = student_assessment["date_submitted"].notna() & (student_assessment["date_submitted"] < 0)
            if negative.any():
                findings["warnings"].append(
                    {"table": "studentAssessment", "negative_course_relative_dates": int(negative.sum())}
                )

    student_vle = tables.get("studentVle")
    if student_vle is not None:
        if "sum_click" in student_vle and (student_vle["sum_click"] < 0).any():
            findings["errors"].append({"table": "studentVle", "negative_click_counts": True})
        if "date" in student_vle and (student_vle["date"] < 0).any():
            findings["warnings"].append({"table": "studentVle", "negative_course_relative_dates": True})

    if findings["errors"]:
        findings["status"] = "failed"
    else:
        findings["status"] = "passed"
    return findings


def validate_oulad_tables(tables: dict[str, pd.DataFrame]) -> dict[str, Any]:
    """Validate OULAD tables and raise with structured, actionable findings."""

    report = audit_oulad_tables(tables)
    if report["errors"]:
        raise ValueError(f"OULAD data-quality validation failed: {report['errors']}")
    return report
