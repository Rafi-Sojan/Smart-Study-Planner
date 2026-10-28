"""Model-risk and release-quality checks.

These checks are deliberately evidence-aware. A model can pass the numerical
integrity checks while remaining ineligible for production because the data is
retrospective, synthetic, uncalibrated, or missing an approved intervention
policy.
"""

from __future__ import annotations

import math
from typing import Any


REQUIRED_TOP_LEVEL_FIELDS = {
    "best_model",
    "models",
    "n_samples",
    "n_train",
    "n_test",
    "target",
}
REQUIRED_MODEL_FIELDS = {
    "accuracy",
    "balanced_accuracy",
    "f1",
    "precision",
    "recall",
    "roc_auc",
    "pr_auc",
    "brier_score",
    "confusion_matrix",
}


def _is_finite_number(value: object) -> bool:
    return isinstance(value, (int, float)) and math.isfinite(float(value))


def _metric_check(
    name: str,
    value: object,
    *,
    minimum: float | None = None,
    maximum: float | None = None,
) -> dict[str, Any]:
    passed = _is_finite_number(value)
    if passed and minimum is not None:
        passed = float(value) >= minimum
    if passed and maximum is not None:
        passed = float(value) <= maximum
    return {
        "name": name,
        "value": float(value) if _is_finite_number(value) else value,
        "minimum": minimum,
        "maximum": maximum,
        "passed": passed,
    }


def assess_model_quality(
    metrics: dict[str, Any],
    *,
    min_pr_auc: float | None = None,
    min_balanced_accuracy: float | None = None,
    max_expected_calibration_error: float | None = None,
) -> dict[str, Any]:
    """Return structural, statistical, and deployment-readiness checks.

    Threshold arguments are optional because a universal performance threshold
    would be inappropriate across OULAD, KU Leuven, and synthetic tracks.
    Supplying them creates an explicit release gate for a particular task.
    """

    # Synthetic and early-warning experiments store one evaluation per cutoff.
    # Normalize each cutoff through the same checks used by the full-course
    # report so that a passing experiment cannot hide a failing cutoff.
    if "evaluations" in metrics and "models" not in metrics:
        cutoff_reports: dict[str, Any] = {}
        for cutoff, evaluation in metrics.get("evaluations", {}).items():
            if not isinstance(evaluation, dict):
                cutoff_reports[str(cutoff)] = {
                    "passed": False,
                    "deployment_eligible": False,
                    "checks": [{"name": "evaluation_structure", "passed": False}],
                }
                continue
            normalized = {
                "best_model": evaluation.get("best_model"),
                "models": evaluation.get("models"),
                "n_samples": evaluation.get("n_samples"),
                "n_train": evaluation.get("n_train"),
                "n_test": evaluation.get("n_test"),
                "target": metrics.get("target", "unknown"),
                "evidence_type": metrics.get("evidence_type", "synthetic_development_only"),
                "deployment_claim": metrics.get("deployment_claim", "development_only"),
            }
            cutoff_reports[str(cutoff)] = assess_model_quality(
                normalized,
                min_pr_auc=min_pr_auc,
                min_balanced_accuracy=min_balanced_accuracy,
                max_expected_calibration_error=max_expected_calibration_error,
            )
        return {
            "passed": bool(cutoff_reports) and all(report["passed"] for report in cutoff_reports.values()),
            "deployment_eligible": False,
            "selected_model": None,
            "evidence_type": str(metrics.get("evidence_type", "synthetic_development_only")),
            "deployment_claim": str(metrics.get("deployment_claim", "development_only")),
            "intervention_policy_configured": False,
            "cutoffs": cutoff_reports,
        }

    checks: list[dict[str, Any]] = []
    missing = sorted(REQUIRED_TOP_LEVEL_FIELDS.difference(metrics))
    checks.append({"name": "required_top_level_fields", "missing": missing, "passed": not missing})

    selected_name = metrics.get("best_model")
    models = metrics.get("models")
    selected = models.get(selected_name) if isinstance(models, dict) else None
    checks.append(
        {
            "name": "selected_model_present",
            "value": selected_name,
            "passed": isinstance(selected, dict),
        }
    )

    if isinstance(selected, dict):
        missing_model_fields = sorted(REQUIRED_MODEL_FIELDS.difference(selected))
        checks.append(
            {
                "name": "required_selected_model_fields",
                "missing": missing_model_fields,
                "passed": not missing_model_fields,
            }
        )
        for metric_name in ("accuracy", "balanced_accuracy", "f1", "precision", "recall", "roc_auc", "pr_auc"):
            checks.append(_metric_check(metric_name, selected.get(metric_name), minimum=0.0, maximum=1.0))
        checks.append(_metric_check("brier_score", selected.get("brier_score"), minimum=0.0, maximum=1.0))
        if "expected_calibration_error" in selected:
            checks.append(
                _metric_check(
                    "expected_calibration_error",
                    selected.get("expected_calibration_error"),
                    minimum=0.0,
                    maximum=1.0,
                )
            )
        matrix = selected.get("confusion_matrix")
        matrix_ok = (
            isinstance(matrix, list)
            and len(matrix) == 2
            and all(isinstance(row, list) and len(row) == 2 for row in matrix)
            and all(isinstance(value, int) and value >= 0 for row in matrix for value in row)
            and sum(value for row in matrix for value in row) > 0
        )
        checks.append({"name": "confusion_matrix_integrity", "passed": matrix_ok})
        if min_pr_auc is not None:
            checks.append(_metric_check("pr_auc_gate", selected.get("pr_auc"), minimum=min_pr_auc))
        if min_balanced_accuracy is not None:
            checks.append(
                _metric_check(
                    "balanced_accuracy_gate",
                    selected.get("balanced_accuracy"),
                    minimum=min_balanced_accuracy,
                )
            )
        if max_expected_calibration_error is not None:
            checks.append(
                _metric_check(
                    "calibration_error_gate",
                    selected.get("expected_calibration_error"),
                    maximum=max_expected_calibration_error,
                )
            )

    sample_counts_ok = all(
        isinstance(metrics.get(name), int) and metrics[name] > 0
        for name in ("n_samples", "n_train", "n_test")
    )
    checks.append({"name": "sample_counts_positive", "passed": sample_counts_ok})

    structural_passed = all(bool(check.get("passed")) for check in checks)
    evidence_type = str(metrics.get("evidence_type", "unknown"))
    deployment_claim = str(metrics.get("deployment_claim", "unknown"))
    policy = selected.get("intervention_policy") if isinstance(selected, dict) else None
    policy_configured = isinstance(policy, dict) and policy.get("status") == "configured"
    deployment_eligible = (
        structural_passed
        and evidence_type == "prospective_institutional_validation"
        and deployment_claim == "prospective_validated"
        and policy_configured
    )
    return {
        "passed": structural_passed,
        "deployment_eligible": deployment_eligible,
        "selected_model": selected_name,
        "evidence_type": evidence_type,
        "deployment_claim": deployment_claim,
        "intervention_policy_configured": policy_configured,
        "checks": checks,
    }


def main() -> None:
    import argparse
    import json
    from pathlib import Path

    parser = argparse.ArgumentParser(description="Validate model metrics and release gates")
    parser.add_argument("--metrics", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--min-pr-auc", type=float, default=None)
    parser.add_argument("--min-balanced-accuracy", type=float, default=None)
    parser.add_argument("--max-expected-calibration-error", type=float, default=None)
    parser.add_argument("--require-deployment-eligibility", action="store_true")
    args = parser.parse_args()
    metrics = json.loads(args.metrics.read_text(encoding="utf-8"))
    report = assess_model_quality(
        metrics,
        min_pr_auc=args.min_pr_auc,
        min_balanced_accuracy=args.min_balanced_accuracy,
        max_expected_calibration_error=args.max_expected_calibration_error,
    )
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    if not report["passed"] or (args.require_deployment_eligibility and not report["deployment_eligible"]):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
