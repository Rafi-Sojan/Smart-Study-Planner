"""Student-disjoint baseline models for the synthetic planner dataset."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import ExtraTreesClassifier, HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from src.features.synthetic_features import build_cutoff_features


MODEL_NAMES = (
    "logistic_regression",
    "random_forest",
    "extra_trees",
    "hist_gradient_boosting",
)
IDENTIFIER_COLUMNS = {
    "enrollment_id",
    "student_id",
    "offering_id",
    "course_id",
    "faculty_id",
    "department_id",
    "program_id",
}
TARGET_COLUMNS = {"risk_label", "passed", "withdrawn", "requires_retake"}
DROP_COLUMNS = IDENTIFIER_COLUMNS | TARGET_COLUMNS | {"observation_cutoff_days"}


def student_split(
    frame: pd.DataFrame,
    test_size: float = 0.25,
    random_state: int = 42,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split all enrollments from each student into the same partition."""

    required = {"student_id", "risk_label"}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"Synthetic feature frame is missing columns: {sorted(missing)}")
    student_target = frame.groupby("student_id")["risk_label"].max().rename("student_risk")
    if student_target.nunique() < 2:
        raise ValueError("Student-disjoint splitting requires both student risk classes")
    train_students, test_students = train_test_split(
        student_target.index,
        test_size=test_size,
        random_state=random_state,
        stratify=student_target.to_numpy(),
    )
    train = frame[frame["student_id"].isin(train_students)].copy()
    test = frame[frame["student_id"].isin(test_students)].copy()
    return train, test


def make_pipeline(features: pd.DataFrame, random_state: int = 42, model_name: str = "logistic_regression") -> Pipeline:
    """Create the leakage-safe preprocessing and classifier pipeline."""

    numeric = features.select_dtypes(include="number").columns.tolist()
    categorical = features.select_dtypes(exclude="number").columns.tolist()
    numeric_steps: Any = SimpleImputer(strategy="median")
    if model_name == "logistic_regression":
        numeric_steps = Pipeline(
            [("imputer", SimpleImputer(strategy="median")), ("scaler", StandardScaler())]
        )
    transformers = [
        ("numeric", numeric_steps, numeric),
        (
            "categorical",
            Pipeline(
                [
                    ("imputer", SimpleImputer(strategy="most_frequent")),
                    ("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
                ]
            ),
            categorical,
        ),
    ]
    return Pipeline(
        [
            ("preprocess", ColumnTransformer(transformers, remainder="drop", sparse_threshold=0)),
            ("model", _make_model(model_name, random_state)),
        ]
    )


def _make_model(name: str, random_state: int) -> Any:
    if name == "logistic_regression":
        return LogisticRegression(max_iter=1000, random_state=random_state)
    if name == "random_forest":
        return RandomForestClassifier(n_estimators=200, random_state=random_state, n_jobs=-1)
    if name == "extra_trees":
        return ExtraTreesClassifier(n_estimators=200, random_state=random_state, n_jobs=-1)
    if name == "hist_gradient_boosting":
        return HistGradientBoostingClassifier(max_iter=150, random_state=random_state)
    raise ValueError(f"Unknown synthetic baseline model: {name}")


def _evaluate(model: Pipeline, x_train: pd.DataFrame, y_train: pd.Series, x_test: pd.DataFrame, y_test: pd.Series) -> dict[str, Any]:
    model.fit(x_train, y_train)
    predictions = model.predict(x_test)
    probabilities = model.predict_proba(x_test)[:, 1]
    return {
        "accuracy": float(accuracy_score(y_test, predictions)),
        "precision": float(precision_score(y_test, predictions, zero_division=0)),
        "recall": float(recall_score(y_test, predictions, zero_division=0)),
        "f1": float(f1_score(y_test, predictions, zero_division=0)),
        "balanced_accuracy": float(balanced_accuracy_score(y_test, predictions)),
        "roc_auc": float(roc_auc_score(y_test, probabilities)),
        "confusion_matrix": confusion_matrix(y_test, predictions).tolist(),
    }


def _rank_key(metrics: dict[str, Any]) -> tuple[float, float, float]:
    return tuple(float(metrics[name]) for name in ("roc_auc", "balanced_accuracy", "f1"))


def run_synthetic_baselines(
    data_dir: str | Path,
    cutoffs_days: Iterable[int] = (30, 60, 90),
    random_state: int = 42,
) -> tuple[dict[str, Any], dict[int, dict[str, Pipeline]]]:
    """Train and compare all four synthetic baselines at each cutoff."""

    cutoffs = sorted({int(value) for value in cutoffs_days})
    if not cutoffs or any(value < 0 for value in cutoffs):
        raise ValueError("cutoffs_days must contain non-negative integers")
    feature_sets = build_cutoff_features(data_dir, cutoffs)
    evaluations: dict[str, Any] = {}
    fitted_models: dict[int, dict[str, Pipeline]] = {}

    for cutoff, frame in feature_sets.items():
        train, test = student_split(frame, random_state=random_state)
        x_train = train.drop(columns=[column for column in DROP_COLUMNS if column in train.columns])
        x_test = test.drop(columns=[column for column in DROP_COLUMNS if column in test.columns])
        y_train, y_test = train["risk_label"], test["risk_label"]
        model_results: dict[str, Any] = {}
        fitted_models[cutoff] = {}
        for model_name in MODEL_NAMES:
            pipeline = make_pipeline(x_train, random_state=random_state, model_name=model_name)
            result = _evaluate(pipeline, x_train, y_train, x_test, y_test)
            result.update({"n_samples": int(len(frame)), "n_train": int(len(train)), "n_test": int(len(test))})
            model_results[model_name] = result
            fitted_models[cutoff][model_name] = pipeline

        best_name = max(MODEL_NAMES, key=lambda name: _rank_key(model_results[name]))
        evaluations[str(cutoff)] = {
            "cutoff_days": cutoff,
            "best_model": best_name,
            "n_samples": int(len(frame)),
            "n_train": int(len(train)),
            "n_test": int(len(test)),
            "risk_count": int(frame["risk_label"].sum()),
            "non_risk_count": int((frame["risk_label"] == 0).sum()),
            "models": model_results,
        }

    metrics = {
        "task": "synthetic_enrollment_risk_classification",
        "data_source": "synthetic_indian_university_planner",
        "target": "simulated failed/withdrawn = 1; simulated passed = 0",
        "evaluation": "student-disjoint holdout",
        "cutoffs_days": cutoffs,
        "random_state": random_state,
        "evaluations": evaluations,
    }
    return metrics, fitted_models
