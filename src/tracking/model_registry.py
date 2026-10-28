"""Small MLflow model-registry adapter with explicit release tags."""

from __future__ import annotations

from typing import Any


def register_model_version(
    mlflow: Any,
    model_uri: str,
    registered_name: str,
    *,
    tags: dict[str, str] | None = None,
    alias: str | None = "candidate",
) -> Any:
    """Register a model and attach auditable tags and an optional alias."""

    model_version = mlflow.register_model(model_uri, registered_name)
    client = mlflow.MlflowClient()
    for key, value in (tags or {}).items():
        client.set_model_version_tag(registered_name, model_version.version, key, str(value))
    if alias:
        client.set_registered_model_alias(registered_name, alias, model_version.version)
    return model_version
