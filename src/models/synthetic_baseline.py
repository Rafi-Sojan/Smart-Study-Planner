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
    average_precision_score,
    accuracy_score,
    balanced_accuracy_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from src.data.provenance import build_provenance
from src.features.synthetic_features import build_cutoff_features
from src.models.evaluate import evaluate_at_threshold, select_threshold_by_validation_f1


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
# Sensitive or consent-related fields remain available for subgroup auditing,
# but are excluded from the default predictor matrix.
AUDIT_ONLY_COLUMNS = {"category", "consent_status", "preferred_language"}
AUDIT_ONLY_COLUMNS |= {
    "residence_type",
    "employment_status",
    "study_mode",
    "prior_education_stream",
    "first_generation_student",
    "internet_access_type",
    "financial_aid_status",
}
DROP_COLUMNS = DROP_COLUMNS | AUDIT_ONLY_COLUMNS


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


def student_train_validation_test(
    frame: pd.DataFrame,
    test_size: float = 0.25,
    validation_size: float = 0.20,
    random_state: int = 42,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Split synthetic enrollments into disjoint student train/validation/test sets."""

    required = {"student_id", "risk_label"}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"Synthetic feature frame is missing columns: {sorted(missing)}")
    student_target = frame.groupby("student_id")["risk_label"].max().rename("student_risk")
    if student_target.nunique() < 2:
        raise ValueError("Student-disjoint splitting requires both student risk classes")
    train_validation_students, test_students = train_test_split(
        student_target.index,
        test_size=test_size,
        random_state=random_state,
        stratify=student_target.to_numpy(),
    )
    validation_fraction = validation_size / (1.0 - test_size)
    remaining_target = student_target.loc[train_validation_students]
    train_students, validation_students = train_test_split(
        remaining_target.index,
        test_size=validation_fraction,
        random_state=random_state,
        stratify=remaining_target.to_numpy(),
    )
    train = frame.loc[frame["student_id"].isin(train_students)].copy()
    validation = frame.loc[frame["student_id"].isin(validation_students)].copy()
    test = frame.loc[frame["student_id"].isin(test_students)].copy()
    return train, validation, test


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


def _group_metrics(y_true: pd.Series, predictions: Any, frame: pd.DataFrame) -> dict[str, Any]:
    """Return descriptive subgroup error rates without using groups as inputs."""

    result: dict[str, Any] = {}
    prediction_series = pd.Series(predictions, index=y_true.index)
    for column in ("category", "residence_type", "employment_status", "study_mode"):
        if column not in frame.columns:
            continue
        groups: dict[str, Any] = {}
        grouped_frame = frame[[column]].copy()
        grouped_frame[column] = grouped_frame[column].astype("string").fillna("<missing>")
        for value, indices in grouped_frame.groupby(column).groups.items():
            actual = y_true.loc[indices]
            predicted = prediction_series.loc[indices]
            groups[str(value)] = {
                "n": int(len(indices)),
                "positive_rate": float(predicted.mean()),
                "recall": float(recall_score(actual, predicted, zero_division=0)),
                "false_positive_rate": float(
                    ((predicted == 1) & (actual == 0)).sum() / max(int((actual == 0).sum()), 1)
                ),
            }
        result[column] = groups
    return result


def _threshold_diagnostics(y_true: pd.Series, probabilities: Any) -> list[dict[str, float | int]]:
    """Show operating-point trade-offs; thresholds are not selected on the test set."""

    rows = []
    for threshold in (0.01, 0.02, 0.05, 0.10, 0.20, 0.30, 0.40, 0.50):
        predictions = (probabilities >= threshold).astype(int)
        rows.append(
            {
                "threshold": threshold,
                "predicted_positive_count": int(predictions.sum()),
                "predicted_positive_rate": float(predictions.mean()),
                "precision": float(precision_score(y_true, predictions, zero_division=0)),
                "recall": float(recall_score(y_true, predictions, zero_division=0)),
                "f1": float(f1_score(y_true, predictions, zero_division=0)),
            }
        )
    return rows


def _evaluate(
    model: Pipeline,
    x_train: pd.DataFrame,
    y_train: pd.Series,
    x_test: pd.DataFrame,
    y_test: pd.Series,
    audit_frame: pd.DataFrame,
) -> dict[str, Any]:
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
        "pr_auc": float(average_precision_score(y_test, probabilities)),
        "brier_score": float(brier_score_loss(y_test, probabilities)),
        "confusion_matrix": confusion_matrix(y_test, predictions).tolist(),
        "threshold_diagnostics": _threshold_diagnostics(y_test, probabilities),
        "subgroup_metrics": _group_metrics(y_test, predictions, audit_frame),
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
        train, validation, test = student_train_validation_test(frame, random_state=random_state)
        x_train = train.drop(columns=[column for column in DROP_COLUMNS if column in train.columns])
        x_validation = validation.drop(columns=[column for column in DROP_COLUMNS if column in validation.columns])
        x_test = test.drop(columns=[column for column in DROP_COLUMNS if column in test.columns])
        y_train, y_validation, y_test = (
            train["risk_label"],
            validation["risk_label"],
            test["risk_label"],
        )
        model_results: dict[str, Any] = {}
        fitted_models[cutoff] = {}
        for model_name in MODEL_NAMES:
            pipeline = make_pipeline(x_train, random_state=random_state, model_name=model_name)
            pipeline.fit(x_train, y_train)
            validation_probabilities = pipeline.predict_proba(x_validation)[:, 1]
            validation_predictions = (validation_probabilities >= 0.5).astype(int)
            validation_metrics = {
                "pr_auc": float(average_precision_score(y_validation, validation_probabilities)),
                "roc_auc": float(roc_auc_score(y_validation, validation_probabilities)),
                "balanced_accuracy": float(balanced_accuracy_score(y_validation, validation_predictions)),
                "f1": float(f1_score(y_validation, validation_predictions, zero_division=0)),
            }
            validation_threshold = select_threshold_by_validation_f1(
                y_validation, validation_probabilities
            )
            combined_x = pd.concat([x_train, x_validation], axis=0)
            combined_y = pd.concat([y_train, y_validation], axis=0)
            final_pipeline = make_pipeline(combined_x, random_state=random_state, model_name=model_name)
            result = _evaluate(final_pipeline, combined_x, combined_y, x_test, y_test, audit_frame=test)
            result.update(
                {
                    "validation_pr_auc": validation_metrics["pr_auc"],
                    "validation_roc_auc": validation_metrics["roc_auc"],
                    "validation_balanced_accuracy": validation_metrics["balanced_accuracy"],
                    "validation_f1": validation_metrics["f1"],
                    "validation_selected_threshold": validation_threshold,
                    "test_at_validation_threshold": evaluate_at_threshold(
                        y_test,
                        final_pipeline.predict_proba(x_test)[:, 1],
                        validation_threshold,
                    ),
                    "n_validation": int(len(validation)),
                    "selection_split": "student_disjoint_validation",
                }
            )
            result.update({"n_samples": int(len(frame)), "n_train": int(len(combined_x)), "n_test": int(len(test))})
            model_results[model_name] = result
            fitted_models[cutoff][model_name] = final_pipeline

        best_name = max(
            MODEL_NAMES,
            key=lambda name: tuple(
                float(model_results[name].get(key))
                if model_results[name].get(key) is not None
                else float("-inf")
                for key in (
                    "validation_pr_auc",
                    "validation_roc_auc",
                    "validation_balanced_accuracy",
                    "validation_f1",
                )
            ),
        )
        evaluations[str(cutoff)] = {
            "cutoff_days": cutoff,
            "best_model": best_name,
            "n_samples": int(len(frame)),
            "n_train": int(len(train) + len(validation)),
            "n_validation": int(len(validation)),
            "n_test": int(len(test)),
            "risk_count": int(frame["risk_label"].sum()),
            "non_risk_count": int((frame["risk_label"] == 0).sum()),
            "models": model_results,
        }

    metrics = {
        "task": "synthetic_enrollment_risk_classification",
        "data_source": "synthetic_indian_university_planner",
        "target": "simulated failed/withdrawn = 1; simulated passed = 0",
        "evaluation": "student-disjoint train-validation-locked-test",
        "cutoffs_days": cutoffs,
        "random_state": random_state,
        "provenance": build_provenance(data_dir, "synthetic-planner-enrollment-v2-student-grouped"),
        "evaluations": evaluations,
    }
    return metrics, fitted_models
