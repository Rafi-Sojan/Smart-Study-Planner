"""Metric validation helpers used before publishing monitoring values."""

from __future__ import annotations

from typing import Any


BOUNDED_METRICS = {
    "accuracy",
    "balanced_accuracy",
    "precision",
    "recall",
    "f1",
    "roc_auc",
    "pr_auc",
}


def validate_metric_values(metrics: dict[str, Any]) -> dict[str, Any]:
    """Return a validation report and reject impossible bounded values."""

    errors = []
    for key, value in metrics.items():
        if key in BOUNDED_METRICS and value is not None:
            numeric = float(value)
            if not 0 <= numeric <= 1:
                errors.append({"metric": key, "value": numeric})
    return {"status": "failed" if errors else "passed", "errors": errors}
