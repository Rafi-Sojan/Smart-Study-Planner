"""Evaluation helpers for binary classification."""

from typing import Any

import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    balanced_accuracy_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)


DEFAULT_THRESHOLDS = (0.01, 0.02, 0.05, 0.10, 0.20, 0.30, 0.40, 0.50)


def threshold_diagnostics(
    target: pd.Series,
    probabilities: Any,
    thresholds: tuple[float, ...] = DEFAULT_THRESHOLDS,
) -> list[dict[str, float | int]]:
    """Report operating points without selecting a threshold on the test set."""

    rows: list[dict[str, float | int]] = []
    for threshold in thresholds:
        predictions = (probabilities >= threshold).astype(int)
        rows.append(
            {
                "threshold": float(threshold),
                "predicted_positive_count": int(predictions.sum()),
                "predicted_positive_rate": float(predictions.mean()),
                "precision": float(precision_score(target, predictions, zero_division=0)),
                "recall": float(recall_score(target, predictions, zero_division=0)),
                "f1": float(f1_score(target, predictions, zero_division=0)),
            }
        )
    return rows


def select_threshold_by_validation_f1(
    target: pd.Series,
    probabilities: Any,
    thresholds: tuple[float, ...] = DEFAULT_THRESHOLDS,
) -> float:
    """Select an operating threshold using validation data only."""

    diagnostics = threshold_diagnostics(target, probabilities, thresholds)
    return float(max(diagnostics, key=lambda row: (row["f1"], row["recall"], -row["threshold"]))["threshold"])


def evaluate_at_threshold(target: pd.Series, probabilities: Any, threshold: float) -> dict[str, Any]:
    """Evaluate an explicit threshold chosen outside the test set."""

    predictions = (probabilities >= threshold).astype(int)
    return {
        "threshold": float(threshold),
        "accuracy": float(accuracy_score(target, predictions)),
        "balanced_accuracy": float(balanced_accuracy_score(target, predictions)),
        "precision": float(precision_score(target, predictions, zero_division=0)),
        "recall": float(recall_score(target, predictions, zero_division=0)),
        "f1": float(f1_score(target, predictions, zero_division=0)),
        "confusion_matrix": confusion_matrix(target, predictions).tolist(),
    }


def evaluate_classifier(model: Any, features: pd.DataFrame, target: pd.Series) -> dict[str, Any]:
    """Evaluate a binary classifier with imbalance-aware and diagnostic metrics."""

    predictions = model.predict(features)
    metrics: dict[str, Any] = {
        "accuracy": float(accuracy_score(target, predictions)),
        "balanced_accuracy": float(balanced_accuracy_score(target, predictions)),
        "precision": float(precision_score(target, predictions, zero_division=0)),
        "recall": float(recall_score(target, predictions, zero_division=0)),
        "f1": float(f1_score(target, predictions, zero_division=0)),
        "roc_auc": None,
        "pr_auc": None,
        "brier_score": None,
        "confusion_matrix": confusion_matrix(target, predictions).tolist(),
    }
    if hasattr(model, "predict_proba") and target.nunique() == 2:
        probabilities = model.predict_proba(features)[:, 1]
        metrics["roc_auc"] = float(roc_auc_score(target, probabilities))
        metrics["pr_auc"] = float(average_precision_score(target, probabilities))
        metrics["brier_score"] = float(brier_score_loss(target, probabilities))
        metrics["threshold_diagnostics"] = threshold_diagnostics(target, probabilities)
    else:
        metrics["threshold_diagnostics"] = []
    return metrics
