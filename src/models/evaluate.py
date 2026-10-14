"""Evaluation helpers for binary classification."""

from typing import Any

import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)


def evaluate_classifier(model: Any, features: pd.DataFrame, target: pd.Series) -> dict[str, float | None]:
    predictions = model.predict(features)
    metrics: dict[str, float | None] = {
        "accuracy": float(accuracy_score(target, predictions)),
        "balanced_accuracy": float(balanced_accuracy_score(target, predictions)),
        "precision": float(precision_score(target, predictions, zero_division=0)),
        "recall": float(recall_score(target, predictions, zero_division=0)),
        "f1": float(f1_score(target, predictions, zero_division=0)),
        "roc_auc": None,
    }
    if hasattr(model, "predict_proba") and target.nunique() == 2:
        probabilities = model.predict_proba(features)[:, 1]
        metrics["roc_auc"] = float(roc_auc_score(target, probabilities))
    return metrics
