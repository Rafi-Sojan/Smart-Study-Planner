"""Optional MLflow logging for reproducible training runs.

The training pipeline remains usable offline. MLflow is configured only when
the caller requests tracking explicitly, so tests and local development do
not require DagsHub credentials.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any


def log_training_run(
    metrics: dict[str, Any],
    metrics_path: str | Path | None = None,
    model_path: str | Path | None = None,
    experiment_name: str = "smart-study-planner-oulad",
    run_name: str | None = None,
) -> str:
    """Log a completed baseline run and its artifacts to MLflow.

    Set ``MLFLOW_TRACKING_URI`` for a manual MLflow/DagsHub configuration. If
    it is unset, ``DAGSHUB_REPO_OWNER`` and ``DAGSHUB_REPO_NAME`` are used with
    ``dagshub.init`` to configure the hosted DagsHub MLflow server.
    """

    try:
        import mlflow
    except ModuleNotFoundError as error:  # pragma: no cover - optional path
        raise RuntimeError(
            "MLflow logging requires the MLOps dependencies. "
            "Install requirements.txt before using --mlflow."
        ) from error

    tracking_uri = os.getenv("MLFLOW_TRACKING_URI")
    if tracking_uri:
        mlflow.set_tracking_uri(tracking_uri)
    else:
        owner = os.getenv("DAGSHUB_REPO_OWNER")
        repository = os.getenv("DAGSHUB_REPO_NAME")
        if not owner or not repository:
            raise RuntimeError(
                "Set MLFLOW_TRACKING_URI or both DAGSHUB_REPO_OWNER and "
                "DAGSHUB_REPO_NAME before using --mlflow."
            )
        try:
            import dagshub
        except ModuleNotFoundError as error:  # pragma: no cover - optional path
            raise RuntimeError(
                "DagsHub logging requires the MLOps dependencies. "
                "Install requirements.txt before using --mlflow."
            ) from error
        dagshub.init(
            repo_owner=owner,
            repo_name=repository,
            mlflow=True,
            dvc=False,
        )

    mlflow.set_experiment(experiment_name)
    with mlflow.start_run(run_name=run_name) as active_run:
        mlflow.log_params(
            {
                "task": metrics["task"],
                "target": metrics["target"],
                "best_model": metrics["best_model"],
                "random_state": metrics["random_state"],
                "n_samples": metrics["n_samples"],
                "n_train": metrics["n_train"],
                "n_test": metrics["n_test"],
            }
        )
        for model_name, model_metrics in metrics["models"].items():
            numeric_metrics = {
                f"{model_name}.{key}": float(value)
                for key, value in model_metrics.items()
                if isinstance(value, (int, float)) and key not in {"n_samples", "n_train", "n_test"}
            }
            mlflow.log_metrics(numeric_metrics)

        for artifact in (metrics_path, model_path):
            if artifact is not None and Path(artifact).exists():
                mlflow.log_artifact(str(artifact))

        return active_run.info.run_id
