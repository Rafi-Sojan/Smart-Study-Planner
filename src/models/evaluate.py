"""Evaluation helpers for binary classification."""

from typing import Any

import numpy as np
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


def calibration_summary(
    target: pd.Series,
    probabilities: Any,
    n_bins: int = 10,
) -> dict[str, Any]:
    """Summarize probability calibration without selecting a deployment policy.

    The expected calibration error (ECE) is a descriptive statistic: it compares
    average predicted probability with the observed positive fraction in each
    probability bin. It must be recalculated on a representative validation or
    prospective sample before displaying scores as probabilities.
    """

    if n_bins < 2:
        raise ValueError("n_bins must be at least 2")
    y_true = np.asarray(target, dtype=int)
    y_prob = np.asarray(probabilities, dtype=float)
    if len(y_true) != len(y_prob):
        raise ValueError("target and probabilities must have equal length")
    if np.any((y_prob < 0) | (y_prob > 1)):
        raise ValueError("probabilities must lie between 0 and 1")
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    bin_ids = np.minimum(np.digitize(y_prob, edges[1:-1], right=False), n_bins - 1)
    counts = np.bincount(bin_ids, minlength=n_bins)
    bins: list[dict[str, float | int | None]] = []
    curve_index = 0
    for index, count in enumerate(counts):
        if count:
            predicted_mean = float(y_prob[bin_ids == index].mean())
            observed_rate = float(y_true[bin_ids == index].mean())
            gap = abs(predicted_mean - observed_rate)
            curve_index += 1
        else:
            predicted_mean = None
            observed_rate = None
            gap = None
        bins.append(
            {
                "bin_lower": float(edges[index]),
                "bin_upper": float(edges[index + 1]),
                "count": int(count),
                "mean_predicted_probability": predicted_mean,
                "observed_positive_rate": observed_rate,
                "absolute_gap": gap,
            }
        )
    ece = float(
        sum(float(row["count"]) * float(row["absolute_gap"]) for row in bins if row["count"])
        / len(y_true)
    ) if len(y_true) else None
    return {
        "n_bins": int(n_bins),
        "expected_calibration_error": ece,
        "bins": bins,
        "curve_bins": int(curve_index),
    }


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
        calibration = calibration_summary(target, probabilities)
        metrics["expected_calibration_error"] = calibration["expected_calibration_error"]
        metrics["calibration"] = calibration
        metrics["threshold_diagnostics"] = threshold_diagnostics(target, probabilities)
    else:
        metrics["threshold_diagnostics"] = []
        metrics["expected_calibration_error"] = None
        metrics["calibration"] = None
    return metrics
