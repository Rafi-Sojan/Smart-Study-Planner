"""Small MLflow model-registry adapter with explicit release tags."""

from __future__ import annotations

import math
import re
from typing import Any


MODEL_URI_PATTERN = re.compile(
    r"^models:/([^/@]+)(?:@([A-Za-z0-9._-]+)|/([0-9]+))$"
)
SHA256_PATTERN = re.compile(r"^[0-9a-fA-F]{64}$")


def parse_registered_model_uri(model_uri: str) -> dict[str, str]:
    """Parse an MLflow model URI using an alias or immutable version."""

    match = MODEL_URI_PATTERN.fullmatch(model_uri or "")
    if match is None:
        raise ValueError(
            "MODEL_URI must be models:/<name>@<alias> or models:/<name>/<numeric-version>"
        )
    name, alias, version = match.groups()
    return {
        "name": name,
        "reference_type": "alias" if alias is not None else "version",
        "reference": alias or str(version),
    }


def resolve_registered_model_version(model_uri: str, client: Any | None = None) -> Any:
    """Resolve a registry URI to one concrete MLflow model version."""

    parsed = parse_registered_model_uri(model_uri)
    if client is None:
        try:
            import mlflow
        except ModuleNotFoundError as error:  # pragma: no cover - deployment path
            raise RuntimeError("MLflow is required to inspect a registered model") from error
        client = mlflow.MlflowClient()
    if parsed["reference_type"] == "alias":
        return client.get_model_version_by_alias(parsed["name"], parsed["reference"])
    return client.get_model_version(parsed["name"], parsed["reference"])


def registered_model_metadata(model_uri: str, client: Any | None = None) -> dict[str, Any]:
    """Return deployment-relevant metadata without loading the model artifact."""

    parsed = parse_registered_model_uri(model_uri)
    version = resolve_registered_model_version(model_uri, client=client)
    return {
        "requested_uri": model_uri,
        "name": str(version.name),
        "version": str(version.version),
        "resolved_uri": f"models:/{version.name}/{version.version}",
        "reference_type": parsed["reference_type"],
        "reference": parsed["reference"],
        "run_id": str(version.run_id) if version.run_id else None,
        "status": str(version.status),
        "tags": {str(key): str(value) for key, value in dict(version.tags or {}).items()},
    }


def _boolean_tag(tags: dict[str, str], name: str) -> bool:
    return tags.get(name, "").strip().lower() == "true"


def verify_registered_model(
    model_uri: str,
    *,
    expected_threshold: float | None = None,
    expected_contract_sha256: str | None = None,
    require_deployment_eligible: bool = True,
    require_fairness: bool = True,
    require_immutable_uri: bool = True,
    client: Any | None = None,
) -> dict[str, Any]:
    """Verify registry governance tags before a production model is loaded."""

    metadata = registered_model_metadata(model_uri, client=client)
    tags = metadata["tags"]
    checks: list[dict[str, Any]] = []

    def add(name: str, passed: bool, value: Any = None) -> None:
        checks.append({"name": name, "passed": bool(passed), "value": value})

    add(
        "immutable_numeric_model_version",
        not require_immutable_uri or metadata["reference_type"] == "version",
        metadata["reference_type"],
    )
    add("registry_version_ready", metadata["status"].upper() == "READY", metadata["status"])
    add("registry_run_id_present", bool(metadata["run_id"]), metadata["run_id"])
    add("quality_gate_passed", _boolean_tag(tags, "quality_gate_passed"), tags.get("quality_gate_passed"))
    add(
        "selected_for_release",
        _boolean_tag(tags, "selected_for_release"),
        tags.get("selected_for_release"),
    )
    add(
        "deployment_eligible",
        not require_deployment_eligible or _boolean_tag(tags, "deployment_eligible"),
        tags.get("deployment_eligible"),
    )
    add(
        "fairness_gate_passed",
        not require_fairness or _boolean_tag(tags, "fairness_gate_passed"),
        tags.get("fairness_gate_passed"),
    )

    threshold_text = tags.get("operating_threshold")
    try:
        registry_threshold = float(threshold_text) if threshold_text is not None else None
    except (TypeError, ValueError):
        registry_threshold = None
    threshold_valid = (
        registry_threshold is not None
        and math.isfinite(registry_threshold)
        and 0 < registry_threshold < 1
    )
    add("operating_threshold_present", threshold_valid, threshold_text)
    threshold_source = tags.get("threshold_source", "").strip()
    add(
        "threshold_source_present",
        bool(threshold_source and threshold_source != "not_configured"),
        threshold_source,
    )
    if expected_threshold is not None:
        expected = float(expected_threshold)
        add(
            "operating_threshold_matches_deployment",
            threshold_valid and math.isclose(registry_threshold, expected, rel_tol=0.0, abs_tol=1e-12),
            {"registry": registry_threshold, "deployment": expected},
        )

    contract_hash = tags.get("feature_contract_sha256")
    add(
        "feature_contract_hash_present",
        bool(contract_hash and SHA256_PATTERN.fullmatch(contract_hash)),
        contract_hash,
    )
    try:
        feature_count = int(tags.get("feature_count", ""))
    except (TypeError, ValueError):
        feature_count = None
    add(
        "feature_count_present",
        feature_count is not None and feature_count > 0,
        tags.get("feature_count"),
    )
    if expected_contract_sha256 is not None:
        add(
            "feature_contract_hash_matches",
            contract_hash == expected_contract_sha256,
            {"registry": contract_hash, "expected": expected_contract_sha256},
        )
    add("evidence_type_present", bool(tags.get("evidence_type")), tags.get("evidence_type"))
    add("deployment_claim_present", bool(tags.get("deployment_claim")), tags.get("deployment_claim"))

    return {
        **metadata,
        "operating_threshold": registry_threshold,
        "threshold_source": threshold_source,
        "feature_contract_sha256": contract_hash,
        "feature_count": feature_count,
        "passed": all(check["passed"] for check in checks),
        "checks": checks,
    }



def register_model_version(
    mlflow: Any,
    model_uri: str,
    registered_name: str,
    *,
    tags: dict[str, str] | None = None,
    alias: str | None = "candidate",
) -> Any:
    """Register a model and verify its version metadata."""
    model_version = mlflow.register_model(
        model_uri,
        registered_name,
    )

    client = mlflow.MlflowClient()
    version_number = str(model_version.version)

    expected_tags = {
        str(key): str(value)
        for key, value in (tags or {}).items()
    }

    for key, value in expected_tags.items():
        client.set_model_version_tag(
            registered_name,
            version_number,
            key,
            value,
        )

    # Read back the saved version tags.
    saved_version = client.get_model_version(
        registered_name,
        version_number,
    )
    saved_tags = dict(saved_version.tags or {})

    mismatches = {
        key: {
            "expected": value,
            "actual": saved_tags.get(key),
        }
        for key, value in expected_tags.items()
        if saved_tags.get(key) != value
    }

    if mismatches:
        raise RuntimeError(
            f"MLflow registration incomplete for "
            f"{registered_name}/{version_number}: "
            f"{mismatches}"
        )

    # Assign the alias only after tag verification.
    if alias:
        client.set_registered_model_alias(
            registered_name,
            alias,
            version_number,
        )

    return model_version
