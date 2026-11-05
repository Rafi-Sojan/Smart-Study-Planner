import pandas as pd
import pytest

from src.models.fairness import evaluate_binary_fairness, wilson_interval


def test_wilson_interval_is_bounded_and_defined() -> None:
    lower, upper = wilson_interval(8, 10)
    assert lower is not None and upper is not None
    assert 0 <= lower < 0.8 < upper <= 1
    assert wilson_interval(0, 0) == (None, None)


def test_fairness_report_has_uncertainty_minimum_groups_and_gaps() -> None:
    target = pd.Series(([1] * 50 + [0] * 50) * 2)
    predictions = (
        [1] * 45
        + [0] * 5
        + [1] * 5
        + [0] * 45
        + [1] * 35
        + [0] * 15
        + [1] * 10
        + [0] * 40
    )
    frame = pd.DataFrame({"group": ["A"] * 100 + ["B"] * 100})

    report = evaluate_binary_fairness(
        target,
        predictions,
        frame,
        ["group"],
        min_group_size=30,
        max_equal_opportunity_gap=0.25,
        max_false_positive_rate_gap=0.25,
        max_selection_rate_gap=0.25,
    )

    attribute = report["attributes"]["group"]
    assert attribute["status"] == "evaluated"
    assert attribute["equal_opportunity_gap"] == pytest.approx(0.2)
    assert attribute["groups"]["A"]["true_positive_rate"]["confidence_interval"]["method"] == "wilson_score"
    assert report["summary"]["passed"] is True


def test_small_groups_remain_visible_but_are_not_compared() -> None:
    report = evaluate_binary_fairness(
        pd.Series([0, 1, 0, 1]),
        [0, 1, 1, 0],
        pd.DataFrame({"group": ["A", "A", "B", "B"]}),
        ["group"],
        min_group_size=3,
        min_positive_count=1,
        min_negative_count=1,
    )

    attribute = report["attributes"]["group"]
    assert attribute["status"] == "insufficient_eligible_groups"
    assert set(attribute["groups"]) == {"A", "B"}
    assert report["summary"]["passed"] is False
