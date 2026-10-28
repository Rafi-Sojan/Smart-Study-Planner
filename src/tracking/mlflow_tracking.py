"""Optional MLflow logging for reproducible training runs.

The training pipeline remains usable offline. MLflow is configured only when
the caller requests tracking explicitly, so tests and local development do
not require DagsHub credentials.
"""

from __future__ import annotations

import os
import sys
from tempfile import TemporaryDirectory
from pathlib import Path
from typing import Any

from src.risk.model_risk import assess_model_quality
from src.tracking.model_registry import register_model_version


def _configure_console() -> None:
    """Prevent MLflow's Unicode completion message from breaking Windows runs."""

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def _configure_tracking() -> Any:
    _configure_console()
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
    return mlflow


def _provenance_params(metrics: dict[str, Any]) -> dict[str, str]:
    """Flatten non-sensitive provenance into MLflow parameters."""

    provenance = metrics.get("provenance", {})
    return {
        f"provenance.{key}": str(value)
        for key, value in provenance.items()
        if value is not None
    }


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

    mlflow = _configure_tracking()
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
                **_provenance_params(metrics),
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


def log_baseline_models_run(
    metrics: dict[str, Any],
    fitted_models: dict[str, Any],
    metrics_path: str | Path | None = None,
    model_path: str | Path | None = None,
    experiment_name: str = "smart-study-planner-oulad",
    run_name: str | None = None,
    registered_model_prefix: str = "smart-study-planner-oulad-baseline",
) -> tuple[str, dict[str, str]]:
    """Log and register every fitted full-course baseline model."""

    mlflow = _configure_tracking()
    mlflow.set_experiment(experiment_name)
    quality = assess_model_quality(metrics)
    registered: dict[str, str] = {}
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
                "quality_gate_passed": quality["passed"],
                "deployment_eligible": quality["deployment_eligible"],
                **_provenance_params(metrics),
            }
        )
        for model_name, model_metrics in metrics["models"].items():
            numeric_metrics = {
                f"{model_name}.{key}": float(value)
                for key, value in model_metrics.items()
                if isinstance(value, (int, float))
                and key not in {"n_samples", "n_train", "n_test"}
            }
            mlflow.log_metrics(numeric_metrics)

        for artifact in (metrics_path, model_path):
            if artifact is not None and Path(artifact).exists():
                mlflow.log_artifact(str(artifact))

        for model_name, model in fitted_models.items():
            artifact_path = f"models/{model_name}"
            registered_name = f"{registered_model_prefix}-{model_name}"
            with TemporaryDirectory(prefix="mlflow-model-") as temp_dir:
                model_dir = Path(temp_dir) / "model"
                mlflow.sklearn.save_model(
                    model,
                    path=str(model_dir),
                    serialization_format="pickle",
                )
                mlflow.log_artifacts(str(model_dir), artifact_path=artifact_path)
            model_uri = f"runs:/{active_run.info.run_id}/{artifact_path}"
            register_model_version(
                mlflow,
                model_uri,
                registered_name,
                tags={
                    "quality_gate_passed": str(quality["passed"]).lower(),
                    "deployment_eligible": str(quality["deployment_eligible"]).lower(),
                    "evidence_type": str(metrics.get("evidence_type", "unknown")),
                    "deployment_claim": str(metrics.get("deployment_claim", "unknown")),
                },
            )
            registered[model_name] = registered_name

        return active_run.info.run_id, registered


def log_early_warning_run(
    metrics: dict[str, Any],
    fitted_models: dict[int, dict[str, Any]],
    metrics_path: str | Path | None = None,
    experiment_name: str = "smart-study-planner-oulad-early-warning",
    run_name: str | None = None,
    register_models: bool = False,
    registered_model_prefix: str = "smart-study-planner-oulad-early-warning",
) -> tuple[str, dict[int, str]]:
    """Log cutoff metrics and optionally register the selected model per cutoff."""

    mlflow = _configure_tracking()
    mlflow.set_experiment(experiment_name)
    registered: dict[int, str] = {}
    with mlflow.start_run(run_name=run_name) as active_run:
        mlflow.log_params(
            {
                "task": metrics["task"],
                "target": metrics["target"],
                "evaluation": metrics["evaluation"],
                "cutoffs_days": ",".join(str(value) for value in metrics["cutoffs_days"]),
            }
        )
        for cutoff_text, evaluation in metrics["evaluations"].items():
            cutoff = int(cutoff_text)
            best_name = evaluation["best_model"]
            mlflow.log_param(f"cutoff_{cutoff}_best_model", best_name)
            for model_name, model_metrics in evaluation["models"].items():
                numeric_metrics = {
                    f"day_{cutoff}.{model_name}.{key}": float(value)
                    for key, value in model_metrics.items()
                    if isinstance(value, (int, float))
                    and key not in {"n_samples", "n_train", "n_test"}
                }
                mlflow.log_metrics(numeric_metrics)

            selected_model = fitted_models[cutoff][best_name]
            artifact_path = f"models/day_{cutoff}/{best_name}"
            registered_name = f"{registered_model_prefix}-day-{cutoff}"
            with TemporaryDirectory(prefix="mlflow-model-") as temp_dir:
                model_dir = Path(temp_dir) / "model"
                mlflow.sklearn.save_model(
                    selected_model,
                    path=str(model_dir),
                    serialization_format="pickle",
                )
                mlflow.log_artifacts(str(model_dir), artifact_path=artifact_path)
            if register_models:
                model_uri = f"runs:/{active_run.info.run_id}/{artifact_path}"
                register_model_version(
                    mlflow,
                    model_uri,
                    registered_name,
                    tags={
                        "development_only": "true",
                        "cutoff_days": str(cutoff),
                        "model_name": best_name,
                    },
                )
                registered[cutoff] = registered_name

        if metrics_path is not None and Path(metrics_path).exists():
            mlflow.log_artifact(str(metrics_path))
        return active_run.info.run_id, registered


def log_synthetic_baseline_run(
    metrics: dict[str, Any],
    fitted_models: dict[int, dict[str, Any]],
    metrics_path: str | Path | None = None,
    experiment_name: str = "smart-study-planner-synthetic-baseline",
    run_name: str | None = None,
    register_models: bool = False,
    registered_model_prefix: str = "smart-study-planner-synthetic-baseline",
) -> tuple[str, dict[int, dict[str, str]]]:
    """Log and optionally register every synthetic model at every cutoff."""

    mlflow = _configure_tracking()
    mlflow.set_experiment(experiment_name)
    registered: dict[int, dict[str, str]] = {}
    with mlflow.start_run(run_name=run_name) as active_run:
        mlflow.log_params(
            {
                "task": metrics["task"],
                "data_source": metrics["data_source"],
                "target": metrics["target"],
                "evaluation": metrics["evaluation"],
                "cutoffs_days": ",".join(str(value) for value in metrics["cutoffs_days"]),
                "random_state": metrics["random_state"],
                **_provenance_params(metrics),
            }
        )
        for cutoff_text, evaluation in metrics["evaluations"].items():
            cutoff = int(cutoff_text)
            mlflow.log_param(f"day_{cutoff}_best_model", evaluation["best_model"])
            for model_name, model_metrics in evaluation["models"].items():
                numeric_metrics = {
                    f"day_{cutoff}.{model_name}.{key}": float(value)
                    for key, value in model_metrics.items()
                    if isinstance(value, (int, float))
                    and key not in {"n_samples", "n_train", "n_test"}
                }
                mlflow.log_metrics(numeric_metrics)

                artifact_path = f"models/day_{cutoff}/{model_name}"
                registered_name = f"{registered_model_prefix}-day-{cutoff}-{model_name}"
                with TemporaryDirectory(prefix="mlflow-model-") as temp_dir:
                    model_dir = Path(temp_dir) / "model"
                    mlflow.sklearn.save_model(
                        fitted_models[cutoff][model_name],
                        path=str(model_dir),
                        serialization_format="pickle",
                    )
                    mlflow.log_artifacts(str(model_dir), artifact_path=artifact_path)
                if register_models:
                    model_uri = f"runs:/{active_run.info.run_id}/{artifact_path}"
                    register_model_version(
                        mlflow,
                        model_uri,
                        registered_name,
                        tags={
                            "development_only": "true",
                            "cutoff_days": str(cutoff),
                            "model_name": model_name,
                        },
                    )
                    registered.setdefault(cutoff, {})[model_name] = registered_name

        if metrics_path is not None and Path(metrics_path).exists():
            mlflow.log_artifact(str(metrics_path))
        return active_run.info.run_id, registered
