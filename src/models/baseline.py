"""Deterministic scikit-learn baseline for OULAD enrollment risk."""

from typing import Any

import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import ExtraTreesClassifier, HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from src.models.evaluate import evaluate_classifier


TARGET = "target_risk"
NON_FEATURE_COLUMNS = {TARGET, "final_result", "id_student", "id_presentation"}


def _split_features(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    if TARGET not in frame:
        raise ValueError(f"Feature frame must include {TARGET!r}")
    labeled = frame.dropna(subset=[TARGET]).copy()
    target = labeled.pop(TARGET).astype(int)
    features = labeled.drop(
        columns=[column for column in NON_FEATURE_COLUMNS if column in labeled],
        errors="ignore",
    )
    if features.empty:
        raise ValueError("No model features remain after removing identifiers and target")
    if target.nunique() < 2:
        raise ValueError("Baseline training requires both risk classes")
    return features, target


def make_baseline_pipeline(features: pd.DataFrame, random_state: int = 42) -> Pipeline:
    numeric = [
        column
        for column in features.select_dtypes(include="number").columns
        if features[column].notna().any()
    ]
    categorical = [
        column
        for column in features.columns
        if column not in numeric and features[column].notna().any()
    ]
    transformers = []
    if numeric:
        transformers.append(
            (
                "numeric",
                Pipeline(
                    [
                        ("imputer", SimpleImputer(strategy="median")),
                        ("scaler", StandardScaler()),
                    ]
                ),
                numeric,
            )
        )
    if categorical:
        transformers.append(
            (
                "categorical",
                Pipeline(
                    [
                        ("imputer", SimpleImputer(strategy="most_frequent")),
                        ("onehot", OneHotEncoder(handle_unknown="ignore")),
                    ]
                ),
                categorical,
            )
        )
    return Pipeline(
        [
            ("preprocess", ColumnTransformer(transformers=transformers)),
            (
                "classifier",
                LogisticRegression(
                    class_weight="balanced",
                    max_iter=1000,
                    random_state=random_state,
                ),
            ),
        ]
    )


def split_baseline_data(
    frame: pd.DataFrame,
    test_size: float = 0.25,
    random_state: int = 42,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.Series, pd.Series]:
    """Create the shared deterministic holdout used by baseline evaluations."""

    features, target = _split_features(frame)
    stratify = target if target.value_counts().min() >= 2 else None
    return train_test_split(
        features,
        target,
        test_size=test_size,
        random_state=random_state,
        stratify=stratify,
    )


def _make_model(name: str, random_state: int) -> Any:
    if name == "logistic_regression":
        return LogisticRegression(
            class_weight="balanced",
            max_iter=1000,
            random_state=random_state,
        )
    if name == "random_forest":
        return RandomForestClassifier(
            class_weight="balanced",
            n_estimators=300,
            n_jobs=-1,
            random_state=random_state,
        )
    if name == "extra_trees":
        return ExtraTreesClassifier(
            class_weight="balanced",
            n_estimators=300,
            n_jobs=-1,
            random_state=random_state,
        )
    if name == "hist_gradient_boosting":
        return HistGradientBoostingClassifier(
            learning_rate=0.05,
            max_iter=200,
            max_leaf_nodes=31,
            random_state=random_state,
        )
    raise ValueError(f"Unknown baseline model: {name}")


MODEL_NAMES = (
    "logistic_regression",
    "random_forest",
    "extra_trees",
    "hist_gradient_boosting",
)


def _make_comparison_pipeline(
    features: pd.DataFrame,
    model_name: str,
    random_state: int,
) -> Pipeline:
    numeric = [
        column
        for column in features.select_dtypes(include="number").columns
        if features[column].notna().any()
    ]
    categorical = [
        column
        for column in features.columns
        if column not in numeric and features[column].notna().any()
    ]
    transformers = []
    if numeric:
        numeric_transformer: Any = SimpleImputer(strategy="median")
        if model_name == "logistic_regression":
            numeric_transformer = Pipeline(
                [
                    ("imputer", SimpleImputer(strategy="median")),
                    ("scaler", StandardScaler()),
                ]
            )
        transformers.append(
            (
                "numeric",
                numeric_transformer,
                numeric,
            )
        )
    if categorical:
        transformers.append(
            (
                "categorical",
                Pipeline(
                    [
                        ("imputer", SimpleImputer(strategy="most_frequent")),
                        ("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
                    ]
                ),
                categorical,
            )
        )
    return Pipeline(
        [
            (
                "preprocess",
                ColumnTransformer(transformers=transformers, sparse_threshold=0),
            ),
            ("classifier", _make_model(model_name, random_state)),
        ]
    )


def train_baselines(
    frame: pd.DataFrame,
    test_size: float = 0.25,
    random_state: int = 42,
) -> tuple[str, dict[str, Pipeline], dict[str, dict[str, float | int | None]]]:
    """Compare four deterministic classifiers on one fixed holdout split."""

    train_features, test_features, train_target, test_target = split_baseline_data(
        frame, test_size=test_size, random_state=random_state
    )
    fitted: dict[str, Pipeline] = {}
    results: dict[str, dict[str, float | int | None]] = {}
    for model_name in MODEL_NAMES:
        model = _make_comparison_pipeline(train_features, model_name, random_state)
        model.fit(train_features, train_target)
        metrics = evaluate_classifier(model, test_features, test_target)
        metrics.update(
            {
                "n_samples": int(len(frame)),
                "n_train": int(len(train_features)),
                "n_test": int(len(test_features)),
                "random_state": random_state,
            }
        )
        fitted[model_name] = model
        results[model_name] = metrics

    def ranking(item: tuple[str, dict[str, float | int | None]]) -> tuple[float, float, float]:
        metrics = item[1]
        return tuple(
            float(metrics[key]) if metrics[key] is not None else float("-inf")
            for key in ("roc_auc", "balanced_accuracy", "f1")
        )

    best_name = max(results.items(), key=ranking)[0]
    return best_name, fitted, results


def train_baseline(
    frame: pd.DataFrame,
    test_size: float = 0.25,
    random_state: int = 42,
) -> tuple[Any, dict[str, float | int | None]]:
    """Fit and evaluate the baseline without touching any external data."""

    train_features, test_features, train_target, test_target = split_baseline_data(
        frame, test_size=test_size, random_state=random_state
    )
    model = make_baseline_pipeline(train_features, random_state=random_state)
    model.fit(train_features, train_target)
    metrics = evaluate_classifier(model, test_features, test_target)
    metrics.update(
        {
            "n_samples": int(len(frame)),
            "n_train": int(len(train_features)),
            "n_test": int(len(test_features)),
            "random_state": random_state,
        }
    )
    return model, metrics
