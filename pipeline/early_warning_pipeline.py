"""Run leakage-aware early-warning evaluations at course-relative cutoffs."""

import argparse
import json
from pathlib import Path
from typing import Any, Iterable

from src.data.cleaner import clean_oulad_tables
from src.data.loader import load_oulad_tables
from src.features.feature_engineering import build_oulad_features
from src.models.baseline import split_time_aware_data, train_time_aware_baselines
from src.tracking.mlflow_tracking import log_early_warning_run


DEFAULT_CUTOFFS = (30, 60, 90)


def _ordered(values: Iterable[object]) -> list[str]:
    return sorted({str(value) for value in values}, key=lambda value: (value[:4], value[4:]))


def run_early_warning(
    data_dir: str | Path,
    metrics_output: str | Path | None = None,
    cutoffs_days: Iterable[int] = DEFAULT_CUTOFFS,
    test_presentations: Iterable[str] | None = None,
    mlflow_enabled: bool = False,
    experiment_name: str = "smart-study-planner-oulad-early-warning",
    run_name: str | None = None,
    register_models: bool = False,
) -> dict[str, Any]:
    """Evaluate full-course labels using only observations before each cutoff."""

    raw_tables = load_oulad_tables(data_dir)
    cleaned_tables = clean_oulad_tables(raw_tables)
    cutoffs = sorted({int(cutoff) for cutoff in cutoffs_days})
    if not cutoffs or any(cutoff < 0 for cutoff in cutoffs):
        raise ValueError("cutoffs_days must contain non-negative integers")

    evaluations: dict[str, Any] = {}
    fitted_models: dict[int, dict[str, Any]] = {}
    for cutoff in cutoffs:
        features = build_oulad_features(
            cleaned_tables,
            clean=False,
            cutoff_days=cutoff,
        )
        best_name, models, model_results = train_time_aware_baselines(
            features,
            test_presentations=test_presentations,
        )
        fitted_models[cutoff] = models
        train_features, test_features, _, _ = split_time_aware_data(
            features,
            test_presentations=test_presentations,
        )
        evaluations[str(cutoff)] = {
            "cutoff_days": cutoff,
            "best_model": best_name,
            "train_presentations": _ordered(train_features["code_presentation"]),
            "test_presentations": _ordered(test_features["code_presentation"]),
            "models": model_results,
        }

    metrics: dict[str, Any] = {
        "task": "early_warning_enrollment_risk_classification",
        "target": "Fail/Withdrawn = 1; Pass/Distinction = 0",
        "evaluation": "time-aware course-presentation holdout",
        "cutoffs_days": cutoffs,
        "evaluations": evaluations,
    }
    if metrics_output is not None:
        path = Path(metrics_output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(metrics, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if mlflow_enabled or register_models:
        run_id, registered = log_early_warning_run(
            metrics,
            fitted_models,
            metrics_path=metrics_output,
            experiment_name=experiment_name,
            run_name=run_name,
            register_models=register_models,
        )
        metrics["mlflow_run_id"] = run_id
        if registered:
            metrics["registered_models"] = {str(key): value for key, value in registered.items()}
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser(description="Run leakage-aware OULAD early-warning evaluation")
    parser.add_argument("--data-dir", type=Path, default=Path("data/processed/oulad"))
    parser.add_argument(
        "--metrics-output",
        type=Path,
        default=Path("models/metrics/early_warning_metrics.json"),
    )
    parser.add_argument("--cutoffs-days", type=int, nargs="+", default=list(DEFAULT_CUTOFFS))
    parser.add_argument("--test-presentations", nargs="+", default=None)
    parser.add_argument("--mlflow", action="store_true", help="Log the evaluation to MLflow/DagsHub")
    parser.add_argument("--experiment-name", default="smart-study-planner-oulad-early-warning")
    parser.add_argument("--run-name", default=None)
    parser.add_argument(
        "--register-models",
        action="store_true",
        help="Register the selected model at each cutoff in MLflow",
    )
    args = parser.parse_args()
    metrics = run_early_warning(
        args.data_dir,
        metrics_output=args.metrics_output,
        cutoffs_days=args.cutoffs_days,
        test_presentations=args.test_presentations,
        mlflow_enabled=args.mlflow,
        experiment_name=args.experiment_name,
        run_name=args.run_name,
        register_models=args.register_models,
    )
    print(json.dumps(metrics, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
