"""CLI for the reproducible OULAD cleaning, feature, and baseline stages."""

import argparse
import json
import pickle
from pathlib import Path
from typing import Any

from src.data.cleaner import clean_oulad_tables
from src.data.loader import load_oulad_tables
from src.features.feature_engineering import build_oulad_features
from src.models.baseline import train_baselines
from src.tracking.mlflow_tracking import log_baseline_models_run, log_training_run


def run_training(
    data_dir: str | Path,
    metrics_output: str | Path | None = None,
    model_output: str | Path | None = None,
    mlflow_enabled: bool = False,
    experiment_name: str = "smart-study-planner-oulad",
    run_name: str | None = None,
    register_models: bool = False,
) -> dict[str, Any]:
    raw_tables = load_oulad_tables(data_dir)
    cleaned_tables = clean_oulad_tables(raw_tables)
    features = build_oulad_features(cleaned_tables, clean=False)
    best_name, models, model_results = train_baselines(features)
    best_model = models[best_name]
    first_result = model_results[best_name]
    metrics = {
        "task": "enrollment_risk_classification",
        "target": "Fail/Withdrawn = 1; Pass/Distinction = 0",
        "best_model": best_name,
        "n_samples": first_result["n_samples"],
        "n_train": first_result["n_train"],
        "n_test": first_result["n_test"],
        "random_state": first_result["random_state"],
        "models": model_results,
    }

    if metrics_output is not None:
        path = Path(metrics_output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(metrics, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if model_output is not None:
        path = Path(model_output)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("wb") as handle:
            pickle.dump(best_model, handle)
    if register_models:
        run_id, registered = log_baseline_models_run(
            metrics,
            models,
            metrics_path=metrics_output,
            model_path=model_output,
            experiment_name=experiment_name,
            run_name=run_name,
        )
        metrics["mlflow_run_id"] = run_id
        metrics["registered_models"] = registered
    elif mlflow_enabled:
        run_id = log_training_run(
            metrics,
            metrics_path=metrics_output,
            model_path=model_output,
            experiment_name=experiment_name,
            run_name=run_name,
        )
        metrics["mlflow_run_id"] = run_id
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser(description="Train the OULAD baseline model")
    parser.add_argument("--data-dir", type=Path, default=Path("data/raw/oulad"))
    parser.add_argument("--metrics-output", type=Path, default=Path("models/metrics/metrics.json"))
    parser.add_argument("--model-output", type=Path, default=Path("models/baseline.pkl"))
    parser.add_argument(
        "--mlflow",
        action="store_true",
        help="Log metrics and model artifacts to MLflow/DagsHub",
    )
    parser.add_argument(
        "--experiment-name",
        default="smart-study-planner-oulad",
        help="MLflow experiment name when --mlflow is enabled",
    )
    parser.add_argument("--run-name", default=None, help="Optional MLflow run name")
    parser.add_argument(
        "--register-models",
        action="store_true",
        help="Register all four full-course baseline models in MLflow",
    )
    args = parser.parse_args()
    metrics = run_training(
        args.data_dir,
        args.metrics_output,
        args.model_output,
        mlflow_enabled=args.mlflow,
        experiment_name=args.experiment_name,
        run_name=args.run_name,
        register_models=args.register_models,
    )
    print(json.dumps(metrics, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
