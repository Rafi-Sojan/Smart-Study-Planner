"""Reusable statistical tests for dataset and external-validity validation.

The functions in this module deliberately separate three questions:

* distribution-shift tests compare feature distributions between cohorts;
* association tests compare observed feature distributions between risk classes;
* model-metric tables compare already-computed predictive results descriptively.

P-values are not evidence of causality or practical importance.  The helper
reports effect sizes and applies Holm correction within each family of tests so
that a notebook does not present a long list of unadjusted findings as if they
were independent confirmations.
"""

from __future__ import annotations

from typing import Any, Iterable

import numpy as np
import pandas as pd
from scipy.stats import chi2_contingency, ks_2samp, mannwhitneyu
from sklearn.model_selection import train_test_split


def _finite_numeric(values: Iterable[Any]) -> np.ndarray:
    """Return finite numeric observations as a one-dimensional float array."""

    numeric = pd.to_numeric(pd.Series(values), errors="coerce").to_numpy(dtype=float)
    return numeric[np.isfinite(numeric)]


def _summary(values: np.ndarray, total_count: int | None = None) -> dict[str, float | int | None]:
    """Return robust descriptive statistics for a numeric sample."""

    if values.size == 0:
        return {
            "n": 0,
            "mean": None,
            "median": None,
            "std": None,
            "q1": None,
            "q3": None,
            "missing_or_non_numeric": int(total_count or 0),
        }
    return {
        "n": int(values.size),
        "mean": float(np.mean(values)),
        "median": float(np.median(values)),
        "std": float(np.std(values, ddof=1)) if values.size > 1 else 0.0,
        "q1": float(np.quantile(values, 0.25)),
        "q3": float(np.quantile(values, 0.75)),
        "missing_or_non_numeric": max(int(total_count or values.size) - int(values.size), 0),
    }


def _holm_adjust(p_values: list[float | None]) -> list[float | None]:
    """Apply Holm-Bonferroni correction while preserving input order."""

    valid = [(index, float(value)) for index, value in enumerate(p_values) if value is not None]
    adjusted: list[float | None] = [None] * len(p_values)
    running_max = 0.0
    for rank, (index, value) in enumerate(sorted(valid, key=lambda item: item[1])):
        corrected = min(1.0, (len(valid) - rank) * value)
        running_max = max(running_max, corrected)
        adjusted[index] = float(running_max)
    return adjusted


def _cliffs_delta(first: np.ndarray, second: np.ndarray, u_statistic: float) -> float:
    """Return a rank-based effect size in [-1, 1].

    Positive values indicate that the comparison sample tends to have larger
    observations than the reference sample.
    """

    denominator = first.size * second.size
    if denominator == 0:
        return float("nan")
    return float(1.0 - 2.0 * u_statistic / denominator)


def numeric_distribution_tests(
    reference: pd.DataFrame,
    comparison: pd.DataFrame,
    columns: Iterable[str],
    *,
    reference_name: str = "reference",
    comparison_name: str = "comparison",
) -> pd.DataFrame:
    """Compare numeric distributions with KS and Mann-Whitney tests.

    The Kolmogorov-Smirnov p-value is the primary shift-test p-value.  The
    Mann-Whitney test is reported as a complementary location/rank test.  Both
    p-value families receive Holm correction.  Cliff's delta and the median
    difference are included because large samples can make tiny shifts
    statistically significant.
    """

    rows: list[dict[str, Any]] = []
    for column in columns:
        if column not in reference or column not in comparison:
            continue
        first_raw = reference[column]
        second_raw = comparison[column]
        first = _finite_numeric(first_raw)
        second = _finite_numeric(second_raw)
        row: dict[str, Any] = {
            "feature": column,
            "reference": reference_name,
            "comparison": comparison_name,
            "reference_n": int(first.size),
            "comparison_n": int(second.size),
        }
        row.update(
            {
                f"reference_{key}": value
                for key, value in _summary(first, len(first_raw)).items()
            }
        )
        row.update(
            {
                f"comparison_{key}": value
                for key, value in _summary(second, len(second_raw)).items()
            }
        )
        row["mean_difference_comparison_minus_reference"] = (
            float(np.mean(second) - np.mean(first)) if first.size and second.size else None
        )
        row["median_difference_comparison_minus_reference"] = (
            float(np.median(second) - np.median(first)) if first.size and second.size else None
        )
        if first.size and second.size:
            ks = ks_2samp(first, second, alternative="two-sided", method="auto")
            mw = mannwhitneyu(first, second, alternative="two-sided", method="auto")
            row["ks_statistic"] = float(ks.statistic)
            row["ks_p_value"] = float(ks.pvalue)
            row["mann_whitney_u"] = float(mw.statistic)
            row["mann_whitney_p_value"] = float(mw.pvalue)
            row["cliffs_delta"] = _cliffs_delta(first, second, float(mw.statistic))
        else:
            row.update(
                {
                    "ks_statistic": None,
                    "ks_p_value": None,
                    "mann_whitney_u": None,
                    "mann_whitney_p_value": None,
                    "cliffs_delta": None,
                }
            )
        rows.append(row)

    result = pd.DataFrame(rows)
    if result.empty:
        return result
    result["ks_p_value_holm"] = _holm_adjust(result["ks_p_value"].tolist())
    result["mann_whitney_p_value_holm"] = _holm_adjust(
        result["mann_whitney_p_value"].tolist()
    )
    result["ks_significant_005"] = result["ks_p_value_holm"].lt(0.05)
    result["mann_whitney_significant_005"] = result["mann_whitney_p_value_holm"].lt(0.05)
    return result


def categorical_distribution_tests(
    reference: pd.DataFrame,
    comparison: pd.DataFrame,
    columns: Iterable[str],
    *,
    reference_name: str = "reference",
    comparison_name: str = "comparison",
) -> pd.DataFrame:
    """Compare categorical distributions with chi-square and Cramer's V."""

    rows: list[dict[str, Any]] = []
    for column in columns:
        if column not in reference or column not in comparison:
            continue
        first = reference[column].astype("string").fillna("<missing>")
        second = comparison[column].astype("string").fillna("<missing>")
        categories = sorted(set(first.unique()).union(second.unique()))
        table = np.array(
            [[int((first == category).sum()) for category in categories],
             [int((second == category).sum()) for category in categories]],
            dtype=int,
        )
        if table.shape[1] >= 2 and table.sum() > 0:
            chi2, p_value, _, _ = chi2_contingency(table, correction=False)
            denominator = table.sum() * min(table.shape[0] - 1, table.shape[1] - 1)
            cramers_v = float(np.sqrt(chi2 / denominator)) if denominator else 0.0
        else:
            chi2, p_value, cramers_v = 0.0, None, None
        rows.append(
            {
                "feature": column,
                "reference": reference_name,
                "comparison": comparison_name,
                "reference_n": int(len(first)),
                "comparison_n": int(len(second)),
                "category_count": int(len(categories)),
                "chi_square": float(chi2),
                "p_value": float(p_value) if p_value is not None else None,
                "cramers_v": cramers_v,
            }
        )
    result = pd.DataFrame(rows)
    if result.empty:
        return result
    result["p_value_holm"] = _holm_adjust(result["p_value"].tolist())
    result["significant_005"] = result["p_value_holm"].lt(0.05)
    return result


def binary_rate_test(
    reference: Iterable[Any],
    comparison: Iterable[Any],
    *,
    reference_name: str = "reference",
    comparison_name: str = "comparison",
) -> dict[str, Any]:
    """Compare binary event rates with a two-row chi-square test."""

    first = pd.to_numeric(pd.Series(reference), errors="coerce").dropna().astype(int)
    second = pd.to_numeric(pd.Series(comparison), errors="coerce").dropna().astype(int)
    first_counts = np.bincount(first.clip(0, 1), minlength=2)
    second_counts = np.bincount(second.clip(0, 1), minlength=2)
    table = np.array([first_counts, second_counts], dtype=int)
    if table.sum() and table.shape == (2, 2):
        chi2, p_value, _, _ = chi2_contingency(table, correction=False)
    else:
        chi2, p_value = 0.0, None
    first_rate = float(first.mean()) if len(first) else None
    second_rate = float(second.mean()) if len(second) else None
    return {
        "reference": reference_name,
        "comparison": comparison_name,
        "reference_n": int(len(first)),
        "comparison_n": int(len(second)),
        "reference_positive_count": int(first_counts[1]),
        "comparison_positive_count": int(second_counts[1]),
        "reference_positive_rate": first_rate,
        "comparison_positive_rate": second_rate,
        "rate_difference_comparison_minus_reference": (
            float(second_rate - first_rate)
            if first_rate is not None and second_rate is not None
            else None
        ),
        "chi_square": float(chi2),
        "p_value": float(p_value) if p_value is not None else None,
        "contingency_table_reference_comparison_rows_nonrisk_risk": table.tolist(),
        "interpretation": "descriptive cohort-rate comparison; not a causal effect estimate",
    }


def numeric_association_tests(
    frame: pd.DataFrame,
    target_column: str,
    columns: Iterable[str],
    *,
    positive_name: str = "risk=1",
    negative_name: str = "risk=0",
) -> pd.DataFrame:
    """Compare numeric feature distributions between two observed target classes."""

    if target_column not in frame:
        raise KeyError(f"target column is missing: {target_column}")
    positive = frame.loc[pd.to_numeric(frame[target_column], errors="coerce").eq(1)]
    negative = frame.loc[pd.to_numeric(frame[target_column], errors="coerce").eq(0)]
    return numeric_distribution_tests(
        negative,
        positive,
        columns,
        reference_name=negative_name,
        comparison_name=positive_name,
    )


def student_disjoint_split(
    frame: pd.DataFrame,
    *,
    student_column: str = "student_id",
    target_column: str = "risk_label",
    test_size: float = 0.20,
    random_state: int = 42,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split an enrollment frame by student, stratifying student-level risk."""

    if student_column not in frame or target_column not in frame:
        raise KeyError(f"frame must contain {student_column!r} and {target_column!r}")
    student_targets = frame.groupby(student_column, as_index=False)[target_column].max()
    train_ids, test_ids = train_test_split(
        student_targets[student_column],
        test_size=test_size,
        random_state=random_state,
        stratify=student_targets[target_column],
    )
    return (
        frame.loc[frame[student_column].isin(train_ids)].copy(),
        frame.loc[frame[student_column].isin(test_ids)].copy(),
    )


def map_oulad_engagement(frame: pd.DataFrame) -> pd.DataFrame:
    """Map OULAD engagement aggregates to the KU/synthetic common contract."""

    result = frame.copy()
    for source, target in (
        ("vle_clicks", "activity_count"),
        ("vle_active_days", "active_day_count"),
        ("vle_resources", "content_count"),
    ):
        result[target] = (
            result[source].fillna(0) if source in result else pd.Series(0, index=result.index)
        )
    result["session_count"] = result["active_day_count"]
    result["mean_daily_activity"] = np.divide(
        result["activity_count"].to_numpy(dtype=float),
        result["active_day_count"].replace(0, np.nan).to_numpy(dtype=float),
    )
    result["mean_daily_activity"] = pd.Series(
        result["mean_daily_activity"], index=result.index
    ).fillna(0.0)
    result["has_activity"] = (result["activity_count"] > 0).astype(int)
    result["target_risk"] = result["target_risk"].astype(int)
    return result


def selected_metric_rows(
    metric_documents: dict[str, dict[str, Any]],
    cutoffs: Iterable[int],
) -> pd.DataFrame:
    """Create a descriptive table of selected-model metrics by dataset."""

    rows: list[dict[str, Any]] = []
    for dataset, document in metric_documents.items():
        evaluations = document.get("evaluations", {})
        for cutoff in sorted({int(value) for value in cutoffs}):
            evaluation = evaluations.get(str(cutoff))
            if not evaluation:
                continue
            model_name = evaluation.get("best_model")
            model_metrics = evaluation.get("models", {}).get(model_name, {})
            rows.append(
                {
                    "dataset": dataset,
                    "cutoff_days": cutoff,
                    "selected_model": model_name,
                    "pr_auc": model_metrics.get("pr_auc"),
                    "roc_auc": model_metrics.get("roc_auc"),
                    "balanced_accuracy": model_metrics.get("balanced_accuracy"),
                    "f1": model_metrics.get("f1"),
                    "brier_score": model_metrics.get("brier_score"),
                }
            )
    return pd.DataFrame(rows)


def json_records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    """Convert a DataFrame to JSON-safe records."""

    if frame.empty:
        return []
    return frame.astype(object).where(pd.notna(frame), None).to_dict("records")

