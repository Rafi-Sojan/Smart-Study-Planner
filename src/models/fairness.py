"""Fairness evaluation for binary student-risk decisions.

The functions in this module treat protected and contextual fields as audit
variables only.  They report uncertainty and minimum-sample rules so that a
small subgroup is not presented as having a reliable error-rate estimate.
No fairness metric establishes that an intervention is fair on its own; the
report is evidence for a documented human review.
"""

from __future__ import annotations

import math
from statistics import NormalDist
from typing import Any, Iterable

import pandas as pd


DEFAULT_CONFIDENCE_LEVEL = 0.95


def wilson_interval(
    successes: int,
    total: int,
    confidence_level: float = DEFAULT_CONFIDENCE_LEVEL,
) -> tuple[float | None, float | None]:
    """Return a Wilson score interval for a binomial proportion.

    Wilson intervals are used instead of the normal approximation because
    subgroup denominators can be modest and rates can be close to zero or one.
    An undefined rate (zero denominator) is represented by ``(None, None)``.
    """

    if total < 0 or successes < 0 or successes > total:
        raise ValueError("successes and total must define a valid binomial count")
    if not 0 < confidence_level < 1:
        raise ValueError("confidence_level must be between zero and one")
    if total == 0:
        return None, None
    z_score = NormalDist().inv_cdf(0.5 + confidence_level / 2.0)
    proportion = successes / total
    denominator = 1.0 + (z_score**2 / total)
    centre = (proportion + z_score**2 / (2.0 * total)) / denominator
    margin = (
        z_score
        * math.sqrt(
            proportion * (1.0 - proportion) / total
            + z_score**2 / (4.0 * total**2)
        )
        / denominator
    )
    return max(0.0, centre - margin), min(1.0, centre + margin)


def _rate(successes: int, total: int, confidence_level: float) -> dict[str, Any]:
    lower, upper = wilson_interval(successes, total, confidence_level)
    return {
        "value": float(successes / total) if total else None,
        "numerator": int(successes),
        "denominator": int(total),
        "confidence_interval": {
            "level": float(confidence_level),
            "lower": lower,
            "upper": upper,
            "method": "wilson_score",
        },
    }


def _gap(groups: dict[str, dict[str, Any]], metric: str) -> float | None:
    values = [
        group[metric]["value"]
        for group in groups.values()
        if group["eligible_for_comparison"] and group[metric]["value"] is not None
    ]
    if len(values) < 2:
        return None
    return float(max(values) - min(values))


def evaluate_binary_fairness(
    target: pd.Series,
    predictions: Any,
    audit_frame: pd.DataFrame,
    attributes: Iterable[str],
    *,
    decision_threshold: float | None = None,
    confidence_level: float = DEFAULT_CONFIDENCE_LEVEL,
    min_group_size: int = 30,
    min_positive_count: int = 5,
    min_negative_count: int = 5,
    max_equal_opportunity_gap: float = 0.20,
    max_false_positive_rate_gap: float = 0.20,
    max_selection_rate_gap: float = 0.20,
) -> dict[str, Any]:
    """Evaluate subgroup decision rates with uncertainty and release rules.

    Equal opportunity is operationalized as the maximum difference in true
    positive rate (recall) between eligible groups.  Selection-rate and false
    positive-rate gaps are reported alongside it.  A group is eligible for
    comparison only if it meets the total, positive, and negative denominator
    rules.  Ineligible groups remain visible in the report but do not produce
    unstable pairwise claims.
    """

    if min_group_size < 1 or min_positive_count < 1 or min_negative_count < 1:
        raise ValueError("fairness minimum counts must be positive")
    for value, name in (
        (max_equal_opportunity_gap, "max_equal_opportunity_gap"),
        (max_false_positive_rate_gap, "max_false_positive_rate_gap"),
        (max_selection_rate_gap, "max_selection_rate_gap"),
    ):
        if not 0 <= value <= 1:
            raise ValueError(f"{name} must be between zero and one")

    actual = pd.Series(target).astype(int)
    if not set(actual.dropna().unique()).issubset({0, 1}):
        raise ValueError("target must contain binary zero/one labels")
    predicted = pd.Series(predictions, index=actual.index).astype(int)
    if not set(predicted.dropna().unique()).issubset({0, 1}):
        raise ValueError("predictions must contain binary zero/one labels")

    aligned = audit_frame.reindex(actual.index)
    attribute_reports: dict[str, Any] = {}
    for attribute in dict.fromkeys(str(value) for value in attributes):
        if attribute not in aligned.columns:
            attribute_reports[attribute] = {
                "status": "missing_attribute",
                "groups": {},
                "eligible_group_count": 0,
                "passed": False,
            }
            continue
        values = aligned[attribute].astype("string").fillna("<missing>")
        groups: dict[str, dict[str, Any]] = {}
        for group_name, indices in values.groupby(values, observed=False).groups.items():
            y_true = actual.loc[indices]
            y_pred = predicted.loc[indices]
            positives = int((y_true == 1).sum())
            negatives = int((y_true == 0).sum())
            predicted_positives = int((y_pred == 1).sum())
            true_positives = int(((y_true == 1) & (y_pred == 1)).sum())
            false_positives = int(((y_true == 0) & (y_pred == 1)).sum())
            correct = int((y_true == y_pred).sum())
            group_size = int(len(indices))
            reasons: list[str] = []
            if group_size < min_group_size:
                reasons.append("group_size_below_minimum")
            if positives < min_positive_count:
                reasons.append("positive_count_below_minimum")
            if negatives < min_negative_count:
                reasons.append("negative_count_below_minimum")
            groups[str(group_name)] = {
                "n": group_size,
                "actual_positive_count": positives,
                "actual_negative_count": negatives,
                "predicted_positive_count": predicted_positives,
                "eligible_for_comparison": not reasons,
                "exclusion_reasons": reasons,
                "selection_rate": _rate(predicted_positives, group_size, confidence_level),
                "true_positive_rate": _rate(true_positives, positives, confidence_level),
                "false_positive_rate": _rate(false_positives, negatives, confidence_level),
                "precision": _rate(true_positives, predicted_positives, confidence_level),
                "accuracy": _rate(correct, group_size, confidence_level),
            }

        eligible_count = sum(
            bool(group["eligible_for_comparison"]) for group in groups.values()
        )
        equal_opportunity_gap = _gap(groups, "true_positive_rate")
        false_positive_rate_gap = _gap(groups, "false_positive_rate")
        selection_rate_gap = _gap(groups, "selection_rate")
        evaluated = eligible_count >= 2
        passed = bool(
            evaluated
            and equal_opportunity_gap is not None
            and equal_opportunity_gap <= max_equal_opportunity_gap
            and false_positive_rate_gap is not None
            and false_positive_rate_gap <= max_false_positive_rate_gap
            and selection_rate_gap is not None
            and selection_rate_gap <= max_selection_rate_gap
        )
        attribute_reports[attribute] = {
            "status": "evaluated" if evaluated else "insufficient_eligible_groups",
            "groups": groups,
            "eligible_group_count": int(eligible_count),
            "equal_opportunity_gap": equal_opportunity_gap,
            "false_positive_rate_gap": false_positive_rate_gap,
            "selection_rate_gap": selection_rate_gap,
            "passed": passed,
        }

    evaluated_reports = [
        report for report in attribute_reports.values() if report["status"] == "evaluated"
    ]

    def maximum(name: str) -> float | None:
        values = [report[name] for report in evaluated_reports if report[name] is not None]
        return float(max(values)) if values else None

    summary = {
        "configured_attribute_count": int(len(attribute_reports)),
        "evaluated_attribute_count": int(len(evaluated_reports)),
        "unevaluable_attributes": sorted(
            name
            for name, report in attribute_reports.items()
            if report["status"] != "evaluated"
        ),
        "max_equal_opportunity_gap": maximum("equal_opportunity_gap"),
        "max_false_positive_rate_gap": maximum("false_positive_rate_gap"),
        "max_selection_rate_gap": maximum("selection_rate_gap"),
        "passed": bool(evaluated_reports) and all(report["passed"] for report in evaluated_reports),
    }
    return {
        "methodology": {
            "decision_threshold": decision_threshold,
            "confidence_level": float(confidence_level),
            "confidence_interval_method": "wilson_score",
            "min_group_size": int(min_group_size),
            "min_positive_count": int(min_positive_count),
            "min_negative_count": int(min_negative_count),
            "max_equal_opportunity_gap": float(max_equal_opportunity_gap),
            "max_false_positive_rate_gap": float(max_false_positive_rate_gap),
            "max_selection_rate_gap": float(max_selection_rate_gap),
            "audit_only": True,
        },
        "attributes": attribute_reports,
        "summary": summary,
        "limitations": (
            "Observed subgroup gaps are descriptive associations, not proof of "
            "causality or intervention fairness. Unevaluable groups require more "
            "representative data and human review before release."
        ),
    }
