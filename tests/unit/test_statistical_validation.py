"""Tests for the shared statistical validation helpers."""

import pandas as pd

from src.validation.statistical import (
    binary_rate_test,
    categorical_distribution_tests,
    numeric_association_tests,
    numeric_distribution_tests,
    student_disjoint_split,
)


def test_numeric_distribution_reports_effect_and_corrected_p_values() -> None:
    reference = pd.DataFrame({"activity": [1, 1, 2, 2, 3, None]})
    comparison = pd.DataFrame({"activity": [10, 11, 12, 13, 14, 15]})

    result = numeric_distribution_tests(reference, comparison, ["activity"])

    assert result.loc[0, "ks_significant_005"]
    assert result.loc[0, "cliffs_delta"] > 0
    assert result.loc[0, "median_difference_comparison_minus_reference"] > 0
    assert result.loc[0, "reference_missing_or_non_numeric"] == 1


def test_categorical_distribution_reports_cramers_v() -> None:
    reference = pd.DataFrame({"mode": ["A"] * 8 + ["B"] * 2})
    comparison = pd.DataFrame({"mode": ["A"] * 2 + ["B"] * 8})

    result = categorical_distribution_tests(reference, comparison, ["mode"])

    assert result.loc[0, "significant_005"]
    assert result.loc[0, "cramers_v"] > 0.5


def test_binary_rate_test_reports_direction() -> None:
    result = binary_rate_test([0, 0, 0, 1], [1, 1, 1, 0])

    assert result["reference_positive_rate"] == 0.25
    assert result["comparison_positive_rate"] == 0.75
    assert result["rate_difference_comparison_minus_reference"] == 0.5


def test_numeric_association_compares_risk_classes() -> None:
    frame = pd.DataFrame(
        {
            "risk_label": [0, 0, 0, 1, 1, 1],
            "sleep": [8, 8, 7, 4, 5, 4],
        }
    )

    result = numeric_association_tests(frame, "risk_label", ["sleep"])

    assert result.loc[0, "median_difference_comparison_minus_reference"] < 0
    assert result.loc[0, "cliffs_delta"] < 0


def test_student_disjoint_split_has_no_student_overlap() -> None:
    frame = pd.DataFrame(
        {
            "student_id": ["a", "a", "b", "b", "c", "c", "d", "d", "e", "e", "f", "f"],
            "risk_label": [0, 1, 0, 0, 1, 1, 0, 1, 0, 0, 1, 1],
            "value": range(12),
        }
    )

    train, test = student_disjoint_split(frame, test_size=0.5, random_state=42)

    assert set(train["student_id"]).isdisjoint(set(test["student_id"]))
    assert len(train) + len(test) == len(frame)
