"""Train and optionally register synthetic planner baseline models."""

from __future__ import annotations

import argparse
import json
import pickle
import sys
from pathlib import Path
from typing import Any, Iterable

from src.models.synthetic_baseline import run_synthetic_baselines
from src.tracking.mlflow_tracking import log_synthetic_baseline_run


def _configure_console() -> None:
    """Allow MLflow's Unicode completion message on Windows PowerShell."""

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def run_synthetic_baseline_pipeline(
    data_dir: str | Path = "data/raw/synthetic",
    metrics_output: str | Path | None = "models/metrics/synthetic_baseline_metrics.json",
    model_dir: str | Path | None = "models/synthetic_baseline",
    cutoffs_days: Iterable[int] = (30, 60, 90),
    random_state: int = 42,
    mlflow_enabled: bool = False,
    experiment_name: str = "smart-study-planner-synthetic-baseline",
    run_name: str | None = None,
    register_models: bool = False,
    registered_model_prefix: str = "smart-study-planner-synthetic-baseline",
) -> dict[str, Any]:
    """Run the synthetic comparison, save outputs, and optionally register models."""

    metrics, fitted_models = run_synthetic_baselines(
        data_dir=data_dir,
        cutoffs_days=cutoffs_days,
        random_state=random_state,
    )
    if metrics_output is not None:
        metrics_path = Path(metrics_output)
        metrics_path.parent.mkdir(parents=True, exist_ok=True)
        metrics_path.write_text(json.dumps(metrics, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if model_dir is not None:
        output_dir = Path(model_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        for cutoff, models in fitted_models.items():
            best_name = metrics["evaluations"][str(cutoff)]["best_model"]
            model_path = output_dir / f"day_{cutoff}_{best_name}.pkl"
            with model_path.open("wb") as handle:
                pickle.dump(models[best_name], handle)

    if mlflow_enabled or register_models:
        run_id, registered = log_synthetic_baseline_run(
            metrics,
            fitted_models,
            metrics_path=metrics_output,
            experiment_name=experiment_name,
            run_name=run_name,
            register_models=register_models,
            registered_model_prefix=registered_model_prefix,
        )
        metrics["mlflow_run_id"] = run_id
        if registered:
            metrics["registered_models"] = {str(key): value for key, value in registered.items()}
    return metrics


def main() -> None:
    _configure_console()
    parser = argparse.ArgumentParser(description="Run synthetic planner baseline experiments")
    parser.add_argument("--data-dir", type=Path, default=Path("data/raw/synthetic"))
    parser.add_argument("--metrics-output", type=Path, default=Path("models/metrics/synthetic_baseline_metrics.json"))
    parser.add_argument("--model-dir", type=Path, default=Path("models/synthetic_baseline"))
    parser.add_argument("--cutoffs-days", type=int, nargs="+", default=[30, 60, 90])
    parser.add_argument("--random-state", type=int, default=42)
    parser.add_argument("--mlflow", action="store_true", help="Log the run to MLflow/DagsHub")
    parser.add_argument("--experiment-name", default="smart-study-planner-synthetic-baseline")
    parser.add_argument("--run-name", default=None)
    parser.add_argument("--register-models", action="store_true", help="Register all four models at every cutoff")
    parser.add_argument("--registered-model-prefix", default="smart-study-planner-synthetic-baseline")
    args = parser.parse_args()
    metrics = run_synthetic_baseline_pipeline(
        data_dir=args.data_dir,
        metrics_output=args.metrics_output,
        model_dir=args.model_dir,
        cutoffs_days=args.cutoffs_days,
        random_state=args.random_state,
        mlflow_enabled=args.mlflow,
        experiment_name=args.experiment_name,
        run_name=args.run_name,
        register_models=args.register_models,
        registered_model_prefix=args.registered_model_prefix,
    )
    print(json.dumps(metrics, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
