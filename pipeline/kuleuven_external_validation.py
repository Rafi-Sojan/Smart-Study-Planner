"""Time-ordered external validation on the KU Leuven public dataset."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd

from src.data.kuleuven import build_kuleuven_cutoff_features
from src.models.baseline import MODEL_NAMES, _make_comparison_pipeline
from src.models.evaluate import evaluate_at_threshold, evaluate_classifier, select_threshold_by_validation_f1
from src.models.policy import intervention_policy_summary


PREDICTOR_COLUMNS = (
    "course_id",
    "activity_count",
    "active_day_count",
    "content_count",
    "session_count",
    "mean_daily_activity",
    "has_activity",
)


def _split_by_presentation(
    frame: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, int]]:
    """Use 1819 for training, 1920 for validation, and 2021 as locked test.

    The source is longitudinal, so some anonymised student IDs recur across
    years.  Repeated IDs are retained for a prospective same-institution
    evaluation, but the ID is excluded from predictors and overlap counts are
    reported so the result is not described as unseen-student generalisation.
    """

    required = {"code_presentation", "target_risk", "id_student"}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"KU Leuven frame is missing: {sorted(missing)}")
    train = frame.loc[frame["code_presentation"].eq("1819")].copy()
    validation = frame.loc[frame["code_presentation"].eq("1920")].copy()
    test = frame.loc[frame["code_presentation"].eq("2021")].copy()
    if train.empty or validation.empty or test.empty:
        raise ValueError("KU Leuven temporal split requires all three presentations")
    for name, partition in (("train", train), ("validation", validation), ("test", test)):
        if partition["target_risk"].nunique() != 2:
            raise ValueError(f"KU Leuven {name} partition must contain both risk classes")
    overlap_counts = {
        "train_validation_student_overlap": int(
            len(set(train["id_student"]) & set(validation["id_student"]))
        ),
        "train_test_student_overlap": int(
            len(set(train["id_student"]) & set(test["id_student"]))
        ),
        "validation_test_student_overlap": int(
            len(set(validation["id_student"]) & set(test["id_student"]))
        ),
    }
    return train, validation, test, overlap_counts


def _features(frame: pd.DataFrame) -> pd.DataFrame:
    return frame.loc[:, list(PREDICTOR_COLUMNS)].copy()


def run_external_validation(
    data_path: str | Path,
    cutoffs_days: tuple[int, ...] = (30, 60, 90),
    random_state: int = 42,
    max_alert_rate: float | None = None,
    false_negative_cost: float | None = None,
    false_positive_cost: float | None = None,
) -> tuple[dict[str, Any], dict[int, dict[str, Any]]]:
    """Compare four baselines and evaluate once on the locked 2021 cohort."""

    feature_sets = build_kuleuven_cutoff_features(data_path, cutoffs_days)
    evaluations: dict[str, Any] = {}
    fitted_models: dict[int, dict[str, Any]] = {}
    for cutoff, frame in feature_sets.items():
        train, validation, test, overlap_counts = _split_by_presentation(frame)
        x_train, x_validation, x_test = map(_features, (train, validation, test))
        y_train, y_validation, y_test = (
            train["target_risk"],
            validation["target_risk"],
            test["target_risk"],
        )
        model_results: dict[str, Any] = {}
        fitted_models[cutoff] = {}
        for model_name in MODEL_NAMES:
            validation_model = _make_comparison_pipeline(x_train, model_name, random_state)
            validation_model.fit(x_train, y_train)
            validation_probabilities = validation_model.predict_proba(x_validation)[:, 1]
            validation_metrics = evaluate_classifier(validation_model, x_validation, y_validation)
            validation_threshold = select_threshold_by_validation_f1(
                y_validation, validation_probabilities
            )
            policy = intervention_policy_summary(
                y_validation,
                validation_probabilities,
                max_alert_rate=max_alert_rate,
                false_negative_cost=false_negative_cost,
                false_positive_cost=false_positive_cost,
            )
            combined_x = pd.concat([x_train, x_validation], ignore_index=True)
            combined_y = pd.concat([y_train, y_validation], ignore_index=True)
            final_model = _make_comparison_pipeline(combined_x, model_name, random_state)
            final_model.fit(combined_x, combined_y)
            test_metrics = evaluate_classifier(final_model, x_test, y_test)
            test_probabilities = final_model.predict_proba(x_test)[:, 1]
            test_metrics.update(
                {
                    "validation_pr_auc": validation_metrics["pr_auc"],
                    "validation_roc_auc": validation_metrics["roc_auc"],
                    "validation_balanced_accuracy": validation_metrics["balanced_accuracy"],
                    "validation_f1": validation_metrics["f1"],
                    "validation_selected_threshold": validation_threshold,
                    "intervention_policy": policy,
                    "test_at_validation_threshold": evaluate_at_threshold(
                        y_test, test_probabilities, validation_threshold
                    ),
                    "n_train": int(len(combined_x)),
                    "n_validation": int(len(x_validation)),
                    "n_test": int(len(x_test)),
                    "selection_split": "1819_train_1920_validation_2021_locked_test",
                    "feature_columns": list(PREDICTOR_COLUMNS),
                }
            )
            if policy["selected_threshold"] is not None:
                test_metrics["test_at_intervention_policy_threshold"] = evaluate_at_threshold(
                    y_test, test_probabilities, float(policy["selected_threshold"])
                )
            model_results[model_name] = test_metrics
            fitted_models[cutoff][model_name] = final_model

        best_name = max(
            MODEL_NAMES,
            key=lambda name: tuple(
                float(model_results[name][key])
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
            "risk_count": int(frame["target_risk"].sum()),
            "non_risk_count": int((frame["target_risk"] == 0).sum()),
            "partition_sizes": {
                "train_1819": int(len(train)),
                "validation_1920": int(len(validation)),
                "test_2021": int(len(test)),
            },
            "student_overlap_counts": overlap_counts,
            "models": model_results,
        }
    metrics = {
        "task": "kuleuven_external_academic_risk_validation",
        "data_source": "KU Leuven Open Data, Private Learners",
        "target": "1 - PASSED; final failed/non-passed outcome",
        "evaluation": "time-ordered prospective validation with a locked 2021 cohort; repeated anonymised students retained and IDs excluded from predictors",
        "cutoffs_days": list(sorted(feature_sets)),
        "random_state": random_state,
        "course_start_anchor": "first recorded LMS activity per course and academic year",
        "external_validity": "assessed_on_authorized_public_dataset",
        "evaluations": evaluations,
    }
    return metrics, fitted_models


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-path", type=Path, default=Path("data/raw/external/kuleuven/dataset.zip"))
    parser.add_argument("--metrics-output", type=Path, default=Path("models/metrics/kuleuven_external_metrics.json"))
    parser.add_argument("--cutoffs-days", type=int, nargs="+", default=[30, 60, 90])
    args = parser.parse_args()
    metrics, _ = run_external_validation(args.data_path, tuple(args.cutoffs_days))
    args.metrics_output.parent.mkdir(parents=True, exist_ok=True)
    args.metrics_output.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(json.dumps({"metrics_output": str(args.metrics_output), "evaluations": metrics["evaluations"]}, indent=2))


if __name__ == "__main__":
    main()
