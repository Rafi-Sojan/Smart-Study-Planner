"""Lightweight, dependency-free data-drift and schema checks."""

from __future__ import annotations

from typing import Any

import pandas as pd


def schema_drift(reference: pd.DataFrame, current: pd.DataFrame) -> dict[str, Any]:
    """Compare columns and dtypes without exposing row-level data."""

    reference_columns = set(reference.columns)
    current_columns = set(current.columns)
    return {
        "missing_columns": sorted(reference_columns - current_columns),
        "unexpected_columns": sorted(current_columns - reference_columns),
        "dtype_changes": {
            column: {"reference": str(reference[column].dtype), "current": str(current[column].dtype)}
            for column in sorted(reference_columns & current_columns)
            if str(reference[column].dtype) != str(current[column].dtype)
        },
    }


def missingness_drift(
    reference: pd.DataFrame,
    current: pd.DataFrame,
    tolerance: float = 0.10,
) -> dict[str, Any]:
    """Report columns whose missing-value share changes materially."""

    columns = sorted(set(reference.columns) & set(current.columns))
    rows = []
    for column in columns:
        reference_rate = float(reference[column].isna().mean())
        current_rate = float(current[column].isna().mean())
        difference = current_rate - reference_rate
        if abs(difference) >= tolerance:
            rows.append(
                {
                    "column": column,
                    "reference_missing_rate": reference_rate,
                    "current_missing_rate": current_rate,
                    "difference": difference,
                }
            )
    return {"tolerance": tolerance, "changed_columns": rows}


def numeric_quantile_drift(
    reference: pd.DataFrame,
    current: pd.DataFrame,
    tolerance: float = 0.25,
) -> dict[str, Any]:
    """Compare robust numeric quantiles using relative IQR displacement."""

    rows = []
    for column in sorted(set(reference.columns) & set(current.columns)):
        if not pd.api.types.is_numeric_dtype(reference[column]) or not pd.api.types.is_numeric_dtype(current[column]):
            continue
        reference_values = reference[column].dropna()
        current_values = current[column].dropna()
        if reference_values.empty or current_values.empty:
            continue
        reference_q = reference_values.quantile([0.25, 0.50, 0.75])
        current_q = current_values.quantile([0.25, 0.50, 0.75])
        scale = max(float(reference_q.loc[0.75] - reference_q.loc[0.25]), 1e-9)
        displacement = abs(float(current_q.loc[0.50] - reference_q.loc[0.50])) / scale
        if displacement >= tolerance:
            rows.append(
                {
                    "column": column,
                    "reference_median": float(reference_q.loc[0.50]),
                    "current_median": float(current_q.loc[0.50]),
                    "relative_median_displacement": displacement,
                }
            )
    return {"tolerance": tolerance, "changed_columns": rows}


def assess_drift(reference: pd.DataFrame, current: pd.DataFrame) -> dict[str, Any]:
    """Return a privacy-preserving drift report for monitoring jobs."""

    report = {
        "schema": schema_drift(reference, current),
        "missingness": missingness_drift(reference, current),
        "numeric_quantiles": numeric_quantile_drift(reference, current),
    }
    report["status"] = "warning" if any(report[key].get("changed_columns") for key in ("missingness", "numeric_quantiles")) or report["schema"]["missing_columns"] or report["schema"]["dtype_changes"] else "ok"
    return report
