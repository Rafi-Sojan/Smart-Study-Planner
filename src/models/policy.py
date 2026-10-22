"""Intervention-policy utilities for capacity- and cost-aware thresholds."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from src.models.evaluate import DEFAULT_THRESHOLDS


def intervention_policy_summary(
    target: pd.Series,
    probabilities: Any,
    *,
    max_alert_rate: float | None = None,
    false_negative_cost: float | None = None,
    false_positive_cost: float | None = None,
    thresholds: tuple[float, ...] = DEFAULT_THRESHOLDS,
) -> dict[str, Any]:
    """Select a validation-only threshold using reviewed operational inputs.

    A policy is deliberately unconfigured unless an alert capacity or both
    error costs are supplied. This prevents the repository from presenting an
    arbitrary threshold as an institutional intervention decision.
    """

    if max_alert_rate is not None and not 0 < max_alert_rate <= 1:
        raise ValueError("max_alert_rate must be greater than 0 and at most 1")
    for name, value in (
        ("false_negative_cost", false_negative_cost),
        ("false_positive_cost", false_positive_cost),
    ):
        if value is not None and value <= 0:
            raise ValueError(f"{name} must be positive")
    if (false_negative_cost is None) != (false_positive_cost is None):
        raise ValueError("both error costs must be supplied together")

    y_true = np.asarray(target, dtype=int)
    y_prob = np.asarray(probabilities, dtype=float)
    rows: list[dict[str, Any]] = []
    for threshold in thresholds:
        predicted = (y_prob >= threshold).astype(int)
        false_positive = int(((predicted == 1) & (y_true == 0)).sum())
        false_negative = int(((predicted == 0) & (y_true == 1)).sum())
        alert_rate = float(predicted.mean()) if len(predicted) else 0.0
        expected_cost = None
        if false_negative_cost is not None and false_positive_cost is not None:
            expected_cost = float(
                false_negative_cost * false_negative + false_positive_cost * false_positive
            ) / max(len(predicted), 1)
        rows.append(
            {
                "threshold": float(threshold),
                "alert_count": int(predicted.sum()),
                "alert_rate": alert_rate,
                "false_positive_count": false_positive,
                "false_negative_count": false_negative,
                "expected_cost_per_observation": expected_cost,
                "within_capacity": (
                    max_alert_rate is None or alert_rate <= max_alert_rate
                ),
            }
        )

    configured = max_alert_rate is not None or false_negative_cost is not None
    result: dict[str, Any] = {
        "configured": configured,
        "max_alert_rate": max_alert_rate,
        "false_negative_cost": false_negative_cost,
        "false_positive_cost": false_positive_cost,
        "selection_basis": None,
        "selected_threshold": None,
        "validation_diagnostics": rows,
    }
    if not configured:
        result["status"] = "not_configured"
        result["reason"] = "Supply reviewed capacity or error costs before deployment."
        return result

    eligible = [row for row in rows if row["within_capacity"]]
    candidates = eligible or rows
    if false_negative_cost is not None:
        selected = min(
            candidates,
            key=lambda row: (
                float(row["expected_cost_per_observation"]),
                -float(row["threshold"]),
            ),
        )
        result["selection_basis"] = "minimum_validation_expected_cost"
    else:
        # Use as much of the reviewed capacity as possible, retaining recall
        # opportunity instead of silently choosing a zero-alert threshold.
        selected = max(candidates, key=lambda row: (float(row["alert_rate"]), -float(row["threshold"])))
        result["selection_basis"] = "highest_alert_rate_within_capacity"
    result["status"] = "configured"
    result["selected_threshold"] = float(selected["threshold"])
    result["capacity_constraint_satisfied"] = bool(eligible)
    return result
