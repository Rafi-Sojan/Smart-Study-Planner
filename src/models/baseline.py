"""Deterministic scikit-learn baseline for OULAD enrollment risk."""

import re
from typing import Any, Iterable

import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import ExtraTreesClassifier, HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import recall_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from src.models.evaluate import evaluate_at_threshold, evaluate_classifier, select_threshold_by_validation_f1


TARGET = "target_risk"
AUDIT_ONLY_COLUMNS = {
    "gender",
    "age_band",
    "imd_band",
    "disability",
    "region",
}
NON_FEATURE_COLUMNS = {
    TARGET,
    "final_result",
    "id_student",
    "id_presentation",
    *AUDIT_ONLY_COLUMNS,
}


def _audit_group_metrics(
    target: pd.Series,
    predictions: Any,
    frame: pd.DataFrame,
) -> dict[str, Any]:
    """Measure subgroup error rates without using audit fields as predictors."""

    result: dict[str, Any] = {}
    prediction_series = pd.Series(predictions, index=target.index)
    for column in sorted(AUDIT_ONLY_COLUMNS):
        if column not in frame:
            continue
        groups: dict[str, Any] = {}
        grouped_frame = frame.loc[target.index, [column]].copy()
        grouped_frame[column] = grouped_frame[column].astype("string").fillna("<missing>")
        for value, indices in grouped_frame.groupby(column).groups.items():
            actual = target.loc[indices]
            predicted = prediction_series.loc[indices]
            groups[str(value)] = {
                "n": int(len(indices)),
                "recall": float(recall_score(actual, predicted, zero_division=0)),
                "false_positive_rate": float(
                    ((predicted == 1) & (actual == 0)).sum() / max(int((actual == 0).sum()), 1)
                ),
            }
        result[column] = groups
    return result


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

    """Create a grouped holdout so one student's enrollments cannot cross splits."""

    features, target = _split_features(frame)
    if "id_student" not in frame:
        stratify = target if target.value_counts().min() >= 2 else None
        return train_test_split(
            features,
            target,
            test_size=test_size,
            random_state=random_state,
            stratify=stratify,
        )

    groups = frame.loc[features.index, "id_student"].astype(str)
    group_target = pd.DataFrame({"group": groups, "target": target}).groupby("group")["target"].max()
    stratify = group_target if group_target.value_counts().min() >= 2 else None
    train_groups, test_groups = train_test_split(
        group_target.index,
        test_size=test_size,
        random_state=random_state,
        stratify=stratify,
    )
    train_mask = groups.isin(train_groups)
    test_mask = groups.isin(test_groups)
    return features.loc[train_mask], features.loc[test_mask], target.loc[train_mask], target.loc[test_mask]


def split_grouped_train_validation_test(
    frame: pd.DataFrame,
    test_size: float = 0.25,
    validation_size: float = 0.20,
    random_state: int = 42,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.Series, pd.Series, pd.Series]:
    """Create disjoint train, validation, and locked-test partitions by student."""

    features, target = _split_features(frame)
    group_column = "id_student"
    if group_column not in frame:
        groups = pd.Series(features.index.astype(str), index=features.index)
    else:
        groups = frame.loc[features.index, group_column].astype(str)
    group_target = pd.DataFrame({"group": groups, "target": target}).groupby("group")["target"].max()
    stratify = group_target if group_target.value_counts().min() >= 2 else None
    train_val_groups, test_groups = train_test_split(
        group_target.index,
        test_size=test_size,
        random_state=random_state,
        stratify=stratify,
    )
    remaining_target = group_target.loc[train_val_groups]
    validation_fraction = validation_size / (1.0 - test_size)
    stratify_remaining = remaining_target if remaining_target.value_counts().min() >= 2 else None
    train_groups, validation_groups = train_test_split(
        remaining_target.index,
        test_size=validation_fraction,
        random_state=random_state,
        stratify=stratify_remaining,
    )
    train_mask = groups.isin(train_groups)
    validation_mask = groups.isin(validation_groups)
    test_mask = groups.isin(test_groups)
    return (
        features.loc[train_mask],
        features.loc[validation_mask],
        features.loc[test_mask],
        target.loc[train_mask],
        target.loc[validation_mask],
        target.loc[test_mask],
    )


def _presentation_sort_key(value: object) -> tuple[int, str]:
    match = re.fullmatch(r"(\d{4})([A-Za-z])", str(value))
    if match is None:
        return (0, str(value))
    return (int(match.group(1)), match.group(2).upper())


def split_time_aware_data(
    frame: pd.DataFrame,
    test_presentations: Iterable[str] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.Series, pd.Series]:
    """Split by course presentation so later presentations are never in train."""

    if "code_presentation" not in frame:
        raise ValueError("Time-aware splitting requires 'code_presentation'")
    labeled = frame.dropna(subset=[TARGET, "code_presentation"]).copy()
    ordered = sorted(labeled["code_presentation"].astype(str).unique(), key=_presentation_sort_key)
    if len(ordered) < 2:
        raise ValueError("Time-aware splitting requires at least two presentations")
    selected_test = {str(value) for value in (test_presentations or [ordered[-1]])}
    unknown = selected_test.difference(ordered)
    if unknown:
        raise ValueError(f"Unknown test presentation(s): {sorted(unknown)}")
    train_mask = ~labeled["code_presentation"].astype(str).isin(selected_test)
    if not train_mask.any() or train_mask.all():
        raise ValueError("Time-aware split must contain both train and test presentations")
    train_frame = labeled.loc[train_mask]
    test_frame = labeled.loc[~train_mask]
    if "id_student" in labeled:
        test_students = set(test_frame["id_student"].astype(str))
        train_frame = train_frame.loc[~train_frame["id_student"].astype(str).isin(test_students)]
    train_features, train_target = _split_features(train_frame)
    test_features, test_target = _split_features(test_frame)
    if train_target.nunique() < 2 or test_target.nunique() < 2:
        raise ValueError("Time-aware split requires both risk classes in train and test")
    return train_features, test_features, train_target, test_target


def split_time_aware_train_validation_test(
    frame: pd.DataFrame,
    test_presentations: Iterable[str] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.Series, pd.Series, pd.Series]:
    """Use the latest presentation as test and the preceding one as validation."""

    if "code_presentation" not in frame:
        raise ValueError("Time-aware splitting requires 'code_presentation'")
    labeled = frame.dropna(subset=[TARGET, "code_presentation"]).copy()
    ordered = sorted(labeled["code_presentation"].astype(str).unique(), key=_presentation_sort_key)
    selected_test = {str(value) for value in (test_presentations or [ordered[-1]])}
    if len(ordered) < 3 and test_presentations is None:
        raise ValueError("Time-aware train/validation/test splitting requires at least three presentations")
    unknown = selected_test.difference(ordered)
    if unknown:
        raise ValueError(f"Unknown test presentation(s): {sorted(unknown)}")
    available_for_validation = [value for value in ordered if value not in selected_test]
    if not available_for_validation:
        raise ValueError("Time-aware split requires a validation presentation")
    validation_presentation = available_for_validation[-1]
    test_frame = labeled.loc[labeled["code_presentation"].astype(str).isin(selected_test)].copy()
    validation_frame = labeled.loc[labeled["code_presentation"].astype(str).eq(validation_presentation)].copy()
    train_frame = labeled.loc[
        ~labeled["code_presentation"].astype(str).isin(selected_test | {validation_presentation})
    ].copy()
    if "id_student" in labeled:
        test_students = set(test_frame["id_student"].astype(str))
        validation_students = set(validation_frame["id_student"].astype(str))
        train_frame = train_frame.loc[
            ~train_frame["id_student"].astype(str).isin(test_students | validation_students)
        ]
        validation_frame = validation_frame.loc[
            ~validation_frame["id_student"].astype(str).isin(test_students)
        ]
    if train_frame.empty or validation_frame.empty or test_frame.empty:
        raise ValueError("Time-aware split produced an empty partition after student disjointing")
    train_features, train_target = _split_features(train_frame)
    validation_features, validation_target = _split_features(validation_frame)
    test_features, test_target = _split_features(test_frame)
    for name, values in (("train", train_target), ("validation", validation_target), ("test", test_target)):
        if values.nunique() < 2:
            raise ValueError(f"Time-aware {name} partition requires both risk classes")
    return (
        train_features,
        validation_features,
        test_features,
        train_target,
        validation_target,
        test_target,
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
) -> tuple[str, dict[str, Pipeline], dict[str, dict[str, Any]]]:
    """Select on validation data, then evaluate once on a locked grouped test set."""

    (
        train_features,
        validation_features,
        test_features,
        train_target,
        validation_target,
        test_target,
    ) = split_grouped_train_validation_test(
        frame,
        test_size=test_size,
        validation_size=0.20,
        random_state=random_state,
    )
    fitted: dict[str, Pipeline] = {}
    results: dict[str, dict[str, Any]] = {}
    validation_results: dict[str, dict[str, Any]] = {}
    for model_name in MODEL_NAMES:
        model = _make_comparison_pipeline(train_features, model_name, random_state)
        model.fit(train_features, train_target)
        validation_results[model_name] = evaluate_classifier(model, validation_features, validation_target)
        validation_probabilities = model.predict_proba(validation_features)[:, 1]
        validation_threshold = select_threshold_by_validation_f1(
            validation_target, validation_probabilities
        )

        combined_features = pd.concat([train_features, validation_features], axis=0)
        combined_target = pd.concat([train_target, validation_target], axis=0)
        final_model = _make_comparison_pipeline(combined_features, model_name, random_state)
        final_model.fit(combined_features, combined_target)
        metrics = evaluate_classifier(final_model, test_features, test_target)
        test_probabilities = final_model.predict_proba(test_features)[:, 1]
        metrics["subgroup_metrics"] = _audit_group_metrics(
            test_target,
            final_model.predict(test_features),
            frame,
        )
        metrics.update(
            {
                "validation_pr_auc": validation_results[model_name].get("pr_auc"),
                "validation_roc_auc": validation_results[model_name].get("roc_auc"),
                "validation_balanced_accuracy": validation_results[model_name].get("balanced_accuracy"),
                "validation_f1": validation_results[model_name].get("f1"),
                "validation_selected_threshold": validation_threshold,
                "test_at_validation_threshold": evaluate_at_threshold(
                    test_target, test_probabilities, validation_threshold
                ),
                "n_samples": int(len(frame)),
                "n_train": int(len(combined_features)),
                "n_validation": int(len(validation_features)),
                "n_test": int(len(test_features)),
                "random_state": random_state,
                "selection_split": "grouped_validation",
            }
        )
        fitted[model_name] = final_model
        results[model_name] = metrics

    def ranking(item: tuple[str, dict[str, Any]]) -> tuple[float, float, float, float]:
        metrics = item[1]
        return tuple(
            float(metrics.get(key)) if metrics.get(key) is not None else float("-inf")
            for key in (
                "validation_pr_auc",
                "validation_roc_auc",
                "validation_balanced_accuracy",
                "validation_f1",
            )
        )

    best_name = max(results.items(), key=ranking)[0]
    return best_name, fitted, results


def train_time_aware_baselines(
    frame: pd.DataFrame,
    test_presentations: Iterable[str] | None = None,
    random_state: int = 42,
) -> tuple[str, dict[str, Pipeline], dict[str, dict[str, Any]]]:
    """Select on a prior presentation and evaluate on a later locked presentation."""

    (
        train_features,
        validation_features,
        test_features,
        train_target,
        validation_target,
        test_target,
    ) = split_time_aware_train_validation_test(frame, test_presentations=test_presentations)
    fitted: dict[str, Pipeline] = {}
    results: dict[str, dict[str, Any]] = {}
    for model_name in MODEL_NAMES:
        model = _make_comparison_pipeline(train_features, model_name, random_state)
        model.fit(train_features, train_target)
        validation_metrics = evaluate_classifier(model, validation_features, validation_target)
        validation_probabilities = model.predict_proba(validation_features)[:, 1]
        validation_threshold = select_threshold_by_validation_f1(
            validation_target, validation_probabilities
        )
        combined_features = pd.concat([train_features, validation_features], axis=0)
        combined_target = pd.concat([train_target, validation_target], axis=0)
        final_model = _make_comparison_pipeline(combined_features, model_name, random_state)
        final_model.fit(combined_features, combined_target)
        metrics = evaluate_classifier(final_model, test_features, test_target)
        test_probabilities = final_model.predict_proba(test_features)[:, 1]
        metrics["subgroup_metrics"] = _audit_group_metrics(
            test_target,
            final_model.predict(test_features),
            frame,
        )
        metrics.update(
            {
                "validation_pr_auc": validation_metrics.get("pr_auc"),
                "validation_roc_auc": validation_metrics.get("roc_auc"),
                "validation_balanced_accuracy": validation_metrics.get("balanced_accuracy"),
                "validation_f1": validation_metrics.get("f1"),
                "validation_selected_threshold": validation_threshold,
                "test_at_validation_threshold": evaluate_at_threshold(
                    test_target, test_probabilities, validation_threshold
                ),
                "n_samples": int(len(train_features) + len(validation_features) + len(test_features)),
                "n_train": int(len(combined_features)),
                "n_validation": int(len(validation_features)),
                "n_test": int(len(test_features)),
                "random_state": random_state,
                "selection_split": "time_ordered_validation",
            }
        )
        fitted[model_name] = final_model
        results[model_name] = metrics

    def ranking(item: tuple[str, dict[str, Any]]) -> tuple[float, float, float, float]:
        metrics = item[1]
        return tuple(
            float(metrics.get(key)) if metrics.get(key) is not None else float("-inf")
            for key in (
                "validation_pr_auc",
                "validation_roc_auc",
                "validation_balanced_accuracy",
                "validation_f1",
            )
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
