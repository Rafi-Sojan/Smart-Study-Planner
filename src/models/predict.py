"""Trusted model loading and inference helpers.

Pickle is executable serialization. Loading is therefore opt-in and requires
an explicit trusted-artifact setting plus an optional SHA-256 verification.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import pickle
import re
from pathlib import Path
from typing import Any

import pandas as pd


FEATURE_NAME_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,127}$")
BLOCKED_INFERENCE_FEATURES = {
    "id_student",
    "student_id",
    "enrollment_id",
    "target",
    "target_risk",
    "risk_label",
    "final_result",
    "passed",
    "withdrawn",
    "requires_retake",
    "date_unregistration",
}


class FeatureContractError(ValueError):
    """Raised when an inference payload does not match the trained model."""


def file_sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_trusted_model(
    path: str | Path,
    *,
    allow_pickle: bool | None = None,
    expected_sha256: str | None = None,
) -> Any:
    """Load a model only when explicit trust and integrity checks pass."""

    allow = allow_pickle if allow_pickle is not None else os.getenv("ALLOW_TRUSTED_PICKLE_MODEL") == "1"
    if not allow:
        raise RuntimeError(
            "Refusing to load pickle model. Set ALLOW_TRUSTED_PICKLE_MODEL=1 "
            "only for an artifact obtained from a trusted registry."
        )
    model_path = Path(path)
    if not model_path.is_file():
        raise FileNotFoundError(model_path)
    expected = expected_sha256 or os.getenv("MODEL_SHA256")
    if expected and file_sha256(model_path).lower() != expected.lower():
        raise ValueError("Model SHA-256 does not match MODEL_SHA256")
    with model_path.open("rb") as handle:
        return pickle.load(handle)


def load_registered_model(model_uri: str) -> Any:
    """Load a model from an MLflow registry or run artifact URI.

    The URI and credentials are supplied through deployment configuration;
    no registry credentials or model artifacts are baked into the image.
    """

    if not model_uri or not model_uri.startswith(("models:/", "runs:/")):
        raise ValueError("MODEL_URI must be an MLflow models:/ or runs:/ URI")
    try:
        import mlflow.sklearn
    except ModuleNotFoundError as error:  # pragma: no cover - deployment path
        raise RuntimeError("MLflow is required when MODEL_URI is configured") from error
    return mlflow.sklearn.load_model(model_uri)


def expected_model_features(model: Any) -> tuple[str, ...]:
    """Return the ordered fitted input columns exposed by a model pipeline."""

    names = getattr(model, "feature_names_in_", None)
    if names is None and hasattr(model, "named_steps"):
        preprocess = model.named_steps.get("preprocess")
        names = getattr(preprocess, "feature_names_in_", None)
    if names is None:
        return ()
    return tuple(str(value) for value in names)


def feature_contract(model: Any) -> dict[str, Any]:
    """Build a stable, non-secret contract for a fitted model's raw inputs."""

    features = expected_model_features(model)
    canonical = json.dumps(list(features), separators=(",", ":"), ensure_ascii=True)
    return {
        "feature_names": list(features),
        "feature_count": len(features),
        "sha256": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        "source": "sklearn_feature_names_in" if features else "unavailable",
    }


def validate_threshold(threshold: float) -> float:
    """Validate a configured binary-decision threshold."""

    value = float(threshold)
    if not math.isfinite(value) or not 0 < value < 1:
        raise ValueError("MODEL_THRESHOLD must be a finite value strictly between zero and one")
    return value


def validate_feature_payload(
    features: dict[str, Any],
    expected_features: tuple[str, ...] | list[str] = (),
) -> None:
    """Reject identifiers, nested values, and model-contract mismatches."""

    if not features:
        raise FeatureContractError("At least one feature is required")
    invalid_names = sorted(name for name in features if not FEATURE_NAME_PATTERN.fullmatch(name))
    if invalid_names:
        raise FeatureContractError(f"Invalid feature names: {invalid_names}")
    blocked = sorted(set(features).intersection(BLOCKED_INFERENCE_FEATURES))
    if blocked:
        raise FeatureContractError(
            f"Identifiers, outcomes, and post-outcome fields are forbidden: {blocked}"
        )

    expected = tuple(str(value) for value in expected_features)
    if expected:
        expected_set = set(expected)
        supplied_set = set(features)
        missing = sorted(expected_set - supplied_set)
        unexpected = sorted(supplied_set - expected_set)
        if missing or unexpected:
            raise FeatureContractError(
                f"Feature contract mismatch; missing={missing}, unexpected={unexpected}"
            )

    for name, value in features.items():
        if isinstance(value, (dict, list, tuple, set)):
            raise FeatureContractError(f"Feature {name!r} must be a scalar value")
        if isinstance(value, float) and not math.isfinite(value):
            raise FeatureContractError(f"Feature {name!r} must be finite")
        if isinstance(value, str) and len(value) > 256:
            raise FeatureContractError(f"Feature {name!r} exceeds 256 characters")


def predict_risk(model: Any, features: dict[str, Any], threshold: float) -> dict[str, float | int]:
    """Predict one feature dictionary without accepting identifiers or raw paths."""

    threshold = validate_threshold(threshold)
    validate_feature_payload(features, expected_model_features(model))
    frame = pd.DataFrame([features])
    probabilities = model.predict_proba(frame)[:, 1]
    score = float(probabilities[0])
    if not math.isfinite(score) or not 0 <= score <= 1:
        raise RuntimeError("Model returned an invalid risk probability")
    return {"risk_score": score, "threshold": threshold, "alert": int(score >= threshold)}
