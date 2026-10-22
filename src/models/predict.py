"""Trusted model loading and inference helpers.

Pickle is executable serialization. Loading is therefore opt-in and requires
an explicit trusted-artifact setting plus an optional SHA-256 verification.
"""

from __future__ import annotations

import hashlib
import os
import pickle
from pathlib import Path
from typing import Any

import pandas as pd


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


def predict_risk(model: Any, features: dict[str, Any], threshold: float) -> dict[str, float | int]:
    """Predict one feature dictionary without accepting identifiers or raw paths."""

    frame = pd.DataFrame([features])
    probabilities = model.predict_proba(frame)[:, 1]
    score = float(probabilities[0])
    return {"risk_score": score, "threshold": float(threshold), "alert": int(score >= threshold)}
