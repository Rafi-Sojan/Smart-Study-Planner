"""Verify every immutable registered model in a deployment catalog."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Callable

from pipeline.verify_registered_model import run_verification
from src.api.model_catalog import ModelSpec, parse_model_catalog


def run_catalog_verification(
    raw_catalog: str,
    *,
    default_model_id: str | None = None,
    verifier: Callable[..., dict[str, Any]] = run_verification,
) -> dict[str, Any]:
    """Verify governance metadata and artifacts for every catalog entry."""

    specs, selected_default = parse_model_catalog(
        raw_catalog,
        default_override=default_model_id,
    )
    reports: list[dict[str, Any]] = []
    for spec in specs:
        if spec.model_uri is None:
            raise ValueError(
                f"Production catalog model {spec.model_id!r} must use model_uri"
            )
        report = verifier(
            spec.model_uri,
            expected_threshold=spec.threshold,
            require_deployment_eligible=True,
            require_fairness=True,
            require_immutable_uri=True,
            load_model=True,
        )
        reports.append(_catalog_report(spec, report))
    return {
        "passed": all(item["verification"]["passed"] for item in reports),
        "default_model_id": selected_default,
        "models": reports,
    }


def _catalog_report(spec: ModelSpec, report: dict[str, Any]) -> dict[str, Any]:
    return {
        "model_id": spec.model_id,
        "label": spec.label,
        "dataset": spec.dataset,
        "cutoff_days": spec.cutoff_days,
        "verification": report,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    raw_catalog = os.getenv("MODEL_CATALOG_JSON", "").strip()
    if not raw_catalog:
        raise SystemExit("MODEL_CATALOG_JSON is required")
    report = run_catalog_verification(
        raw_catalog,
        default_model_id=os.getenv("DEFAULT_MODEL_ID") or None,
    )
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
