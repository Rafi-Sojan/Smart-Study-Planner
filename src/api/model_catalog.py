"""Validated runtime catalog for user-selectable serving models."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.models.predict import (
    feature_contract,
    load_registered_model,
    load_trusted_model,
    validate_model_feature_contract,
    validate_threshold,
)
from src.tracking.model_registry import verify_registered_model


MODEL_ID_PATTERN = re.compile(r"^[a-z][a-z0-9-]{0,62}$")
MAX_CATALOG_MODELS = 12
MAX_CATALOG_JSON_BYTES = 65_536
_SPEC_KEYS = {
    "id",
    "label",
    "description",
    "dataset",
    "cutoff_days",
    "model_uri",
    "model_path",
    "model_sha256",
    "threshold",
    "model_version",
}


@dataclass(frozen=True)
class ModelSpec:
    """Configuration for one allowlisted model before artifact loading."""

    model_id: str
    label: str
    description: str
    dataset: str | None
    cutoff_days: int | None
    model_uri: str | None
    model_path: str | None
    model_sha256: str | None
    threshold: float | None
    model_version: str | None


@dataclass(frozen=True)
class ModelRuntime:
    """Loaded model plus the metadata required for safe request routing."""

    model_id: str
    label: str
    description: str
    dataset: str | None
    cutoff_days: int | None
    model: Any
    threshold: float
    threshold_source: str
    model_version: str
    model_source: str
    model_metadata: dict[str, Any]
    feature_contract: dict[str, Any]


@dataclass(frozen=True)
class ModelCatalog:
    """Immutable routing view over loaded, explicitly configured models."""

    models: dict[str, ModelRuntime]
    default_model_id: str | None

    def __bool__(self) -> bool:
        return bool(self.models)

    def default(self) -> ModelRuntime | None:
        if self.default_model_id is None:
            return None
        return self.models[self.default_model_id]

    def resolve(self, model_id: str | None) -> ModelRuntime:
        selected = model_id or self.default_model_id
        if selected is None or selected not in self.models:
            raise KeyError(selected)
        return self.models[selected]


def _required_text(value: Any, field: str, *, max_length: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Model catalog field {field!r} must be a non-empty string")
    rendered = value.strip()
    if len(rendered) > max_length:
        raise ValueError(f"Model catalog field {field!r} exceeds {max_length} characters")
    return rendered


def _optional_text(value: Any, field: str, *, max_length: int) -> str | None:
    if value is None:
        return None
    return _required_text(value, field, max_length=max_length)


def _parse_spec(raw: Any) -> ModelSpec:
    if not isinstance(raw, dict):
        raise ValueError("Each model catalog entry must be an object")
    unexpected = sorted(set(raw) - _SPEC_KEYS)
    if unexpected:
        raise ValueError(f"Unexpected model catalog fields: {unexpected}")

    model_id = _required_text(raw.get("id"), "id", max_length=63)
    if not MODEL_ID_PATTERN.fullmatch(model_id):
        raise ValueError(
            "Model catalog id must start with a lowercase letter and contain only "
            "lowercase letters, digits, and hyphens"
        )
    model_uri = _optional_text(raw.get("model_uri"), "model_uri", max_length=512)
    model_path = _optional_text(raw.get("model_path"), "model_path", max_length=512)
    if bool(model_uri) == bool(model_path):
        raise ValueError(
            f"Model {model_id!r} must configure exactly one of model_uri or model_path"
        )

    raw_threshold = raw.get("threshold")
    threshold = validate_threshold(float(raw_threshold)) if raw_threshold is not None else None
    raw_cutoff = raw.get("cutoff_days")
    cutoff_days = None
    if raw_cutoff is not None:
        if isinstance(raw_cutoff, bool) or not isinstance(raw_cutoff, int):
            raise ValueError(f"Model {model_id!r} cutoff_days must be an integer")
        cutoff_days = raw_cutoff
        if cutoff_days <= 0 or cutoff_days > 10_000:
            raise ValueError(f"Model {model_id!r} cutoff_days is outside the supported range")

    default_label = model_id.replace("-", " ").title()
    model_sha256 = _optional_text(
        raw.get("model_sha256"), "model_sha256", max_length=64
    )
    if model_sha256 and not re.fullmatch(r"[A-Fa-f0-9]{64}", model_sha256):
        raise ValueError(f"Model {model_id!r} model_sha256 must contain 64 hexadecimal digits")
    return ModelSpec(
        model_id=model_id,
        label=_optional_text(raw.get("label"), "label", max_length=120) or default_label,
        description=_optional_text(
            raw.get("description"), "description", max_length=500
        )
        or "Configured risk-scoring model.",
        dataset=_optional_text(raw.get("dataset"), "dataset", max_length=120),
        cutoff_days=cutoff_days,
        model_uri=model_uri,
        model_path=model_path,
        model_sha256=model_sha256,
        threshold=threshold,
        model_version=_optional_text(
            raw.get("model_version"), "model_version", max_length=160
        ),
    )


def parse_model_catalog(
    raw_catalog: str,
    *,
    default_override: str | None = None,
) -> tuple[list[ModelSpec], str]:
    """Parse and validate catalog JSON without loading model artifacts."""

    if len(raw_catalog.encode("utf-8")) > MAX_CATALOG_JSON_BYTES:
        raise ValueError("MODEL_CATALOG_JSON exceeds 65536 bytes")
    try:
        decoded = json.loads(raw_catalog)
    except json.JSONDecodeError as error:
        raise ValueError("MODEL_CATALOG_JSON is not valid JSON") from error

    configured_default: Any = None
    if isinstance(decoded, list):
        raw_models = decoded
    elif isinstance(decoded, dict):
        unexpected = sorted(set(decoded) - {"default_model_id", "models"})
        if unexpected:
            raise ValueError(f"Unexpected model catalog top-level fields: {unexpected}")
        raw_models = decoded.get("models")
        configured_default = decoded.get("default_model_id")
    else:
        raise ValueError("MODEL_CATALOG_JSON must be an object or array")

    if not isinstance(raw_models, list) or not 1 <= len(raw_models) <= MAX_CATALOG_MODELS:
        raise ValueError(f"Model catalog must contain between 1 and {MAX_CATALOG_MODELS} models")
    specs = [_parse_spec(item) for item in raw_models]
    ids = [spec.model_id for spec in specs]
    if len(ids) != len(set(ids)):
        raise ValueError("Model catalog ids must be unique")

    selected_default = default_override or configured_default or ids[0]
    if not isinstance(selected_default, str) or selected_default not in set(ids):
        raise ValueError("DEFAULT_MODEL_ID must identify a configured catalog model")
    return specs, selected_default


def _load_runtime(spec: ModelSpec, *, production: bool) -> ModelRuntime:
    metadata: dict[str, Any] = {}
    if spec.model_uri:
        verification = verify_registered_model(
            spec.model_uri,
            expected_threshold=spec.threshold,
            require_deployment_eligible=production,
            require_fairness=production,
            require_immutable_uri=production,
        )
        if not verification["passed"]:
            failed = [check["name"] for check in verification["checks"] if not check["passed"]]
            raise RuntimeError(
                f"Registered model verification failed for {spec.model_id!r}: {failed}"
            )
        registry_threshold = verification["operating_threshold"]
        if registry_threshold is None:
            raise RuntimeError(
                f"Registered model {spec.model_id!r} has no approved operating_threshold tag"
            )
        threshold = validate_threshold(registry_threshold)
        threshold_source = "mlflow_registry_tag"
        model_source = verification["resolved_uri"]
        model = load_registered_model(model_source)
        metadata = verification
        model_version = spec.model_version or (
            f"{verification['name']}/{verification['version']}"
        )
    else:
        if production:
            raise RuntimeError(
                f"Production refuses local model_path for catalog model {spec.model_id!r}"
            )
        model = load_trusted_model(
            Path(spec.model_path or ""),
            expected_sha256=spec.model_sha256,
        )
        threshold = validate_threshold(spec.threshold if spec.threshold is not None else 0.5)
        threshold_source = (
            "catalog_configuration" if spec.threshold is not None else "development_default"
        )
        model_source = spec.model_path or ""
        model_version = spec.model_version or spec.model_id

    validate_model_feature_contract(model)
    contract = feature_contract(model)
    if not contract["feature_names"]:
        raise RuntimeError(f"Loaded model {spec.model_id!r} has no raw feature contract")
    registry_contract = metadata.get("feature_contract_sha256")
    if registry_contract and registry_contract != contract["sha256"]:
        raise RuntimeError(
            f"Loaded model {spec.model_id!r} feature contract does not match registry metadata"
        )
    return ModelRuntime(
        model_id=spec.model_id,
        label=spec.label,
        description=spec.description,
        dataset=spec.dataset,
        cutoff_days=spec.cutoff_days,
        model=model,
        threshold=threshold,
        threshold_source=threshold_source,
        model_version=model_version,
        model_source=model_source,
        model_metadata=metadata,
        feature_contract=contract,
    )


def _legacy_spec(*, production: bool) -> ModelSpec | None:
    model_path = os.getenv("MODEL_PATH") or None
    model_uri = os.getenv("MODEL_URI") or None
    if not model_path and not model_uri and Path("/models/model.pkl").is_file():
        model_path = "/models/model.pkl"
    if model_path and model_uri:
        raise RuntimeError("Configure only one of MODEL_PATH or MODEL_URI")
    if production and not model_uri:
        raise RuntimeError("Production requires an immutable registered MODEL_URI")
    if not model_path and not model_uri:
        return None

    raw_threshold = os.getenv("MODEL_THRESHOLD")
    raw_cutoff = os.getenv("MODEL_CUTOFF_DAYS")
    cutoff_days = int(raw_cutoff) if raw_cutoff else None
    if cutoff_days is not None and not 0 < cutoff_days <= 10_000:
        raise RuntimeError("MODEL_CUTOFF_DAYS is outside the supported range")
    return ModelSpec(
        model_id=os.getenv("DEFAULT_MODEL_ID") or "default",
        label=os.getenv("MODEL_LABEL") or "Default risk model",
        description=os.getenv("MODEL_DESCRIPTION")
        or "The model configured for this deployment.",
        dataset=os.getenv("MODEL_DATASET") or None,
        cutoff_days=cutoff_days,
        model_uri=model_uri,
        model_path=model_path,
        model_sha256=os.getenv("MODEL_SHA256") or None,
        threshold=validate_threshold(float(raw_threshold)) if raw_threshold else None,
        model_version=os.getenv("MODEL_VERSION") or None,
    )


def load_model_catalog(*, production: bool) -> ModelCatalog:
    """Load the configured model catalog or the legacy single-model settings."""

    raw_catalog = os.getenv("MODEL_CATALOG_JSON", "").strip()
    if raw_catalog:
        if os.getenv("MODEL_URI") or os.getenv("MODEL_PATH"):
            raise RuntimeError(
                "MODEL_CATALOG_JSON cannot be combined with MODEL_URI or MODEL_PATH"
            )
        specs, default_model_id = parse_model_catalog(
            raw_catalog,
            default_override=os.getenv("DEFAULT_MODEL_ID") or None,
        )
    else:
        spec = _legacy_spec(production=production)
        if spec is None:
            return ModelCatalog(models={}, default_model_id=None)
        if not MODEL_ID_PATTERN.fullmatch(spec.model_id):
            raise RuntimeError("DEFAULT_MODEL_ID is not a valid model id")
        specs = [spec]
        default_model_id = spec.model_id

    runtimes = {
        spec.model_id: _load_runtime(spec, production=production)
        for spec in specs
    }
    return ModelCatalog(models=runtimes, default_model_id=default_model_id)
