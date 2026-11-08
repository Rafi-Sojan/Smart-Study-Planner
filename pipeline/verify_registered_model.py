"""Verify an MLflow model version and its production-governance metadata."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from src.models.predict import feature_contract, validate_model_feature_contract
from src.tracking.model_registry import verify_registered_model


def run_verification(
    model_uri: str,
    *,
    expected_threshold: float | None = None,
    require_deployment_eligible: bool = True,
    require_fairness: bool = True,
    require_immutable_uri: bool = True,
    load_model: bool = True,
) -> dict[str, Any]:
    """Return a registry report and optionally verify the downloaded artifact."""

    try:
        import mlflow
        import mlflow.sklearn
    except ModuleNotFoundError as error:  # pragma: no cover - deployment path
        raise RuntimeError("MLflow is required for registry verification") from error
    tracking_uri = os.getenv("MLFLOW_TRACKING_URI")
    if tracking_uri:
        mlflow.set_tracking_uri(tracking_uri)
    report = verify_registered_model(
        model_uri,
        expected_threshold=expected_threshold,
        require_deployment_eligible=require_deployment_eligible,
        require_fairness=require_fairness,
        require_immutable_uri=require_immutable_uri,
    )
    if load_model:
        model = mlflow.sklearn.load_model(report["resolved_uri"])
        validate_model_feature_contract(model)
        contract = feature_contract(model)
        contract_matches = contract["sha256"] == report["feature_contract_sha256"]
        feature_count_matches = contract["feature_count"] == report["feature_count"]
        report["artifact_verification"] = {
            "loaded": True,
            "feature_count": contract["feature_count"],
            "feature_contract_sha256": contract["sha256"],
            "contract_matches_registry": contract_matches,
            "feature_count_matches_registry": feature_count_matches,
        }
        report["checks"].append(
            {
                "name": "loaded_artifact_contract_matches_registry",
                "passed": contract_matches,
                "value": contract["sha256"],
            }
        )
        report["checks"].append(
            {
                "name": "loaded_artifact_feature_count_matches_registry",
                "passed": feature_count_matches,
                "value": contract["feature_count"],
            }
        )
        report["passed"] = bool(
            report["passed"] and contract_matches and feature_count_matches
        )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-uri", required=True)
    parser.add_argument("--expected-threshold", type=float, default=None)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--allow-ineligible", action="store_true")
    parser.add_argument("--allow-missing-fairness", action="store_true")
    parser.add_argument("--allow-alias", action="store_true")
    parser.add_argument("--skip-model-load", action="store_true")
    args = parser.parse_args()
    report = run_verification(
        args.model_uri,
        expected_threshold=args.expected_threshold,
        require_deployment_eligible=not args.allow_ineligible,
        require_fairness=not args.allow_missing_fairness,
        require_immutable_uri=not args.allow_alias,
        load_model=not args.skip_model_load,
    )
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
