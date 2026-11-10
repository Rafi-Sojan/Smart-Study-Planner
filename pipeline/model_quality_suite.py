"""Generate deterministic model-risk and model-quality assessment reports."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import yaml

from src.risk.model_risk import assess_model_quality


THRESHOLD_FIELDS = (
    "min_pr_auc",
    "min_balanced_accuracy",
    "min_operating_point_recall",
    "max_expected_calibration_error",
)


def _read_mapping(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Quality policy must be a mapping: {path}")
    return payload


def _read_metrics(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Metrics artifact must contain a JSON object: {path}")
    return payload


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _finite_number(value: object) -> bool:
    return isinstance(value, (int, float)) and math.isfinite(float(value))


def _threshold_policy(raw: object) -> tuple[dict[str, Any], dict[str, float | None], bool]:
    policy = raw if isinstance(raw, dict) else {}
    status = str(policy.get("status", "not_approved"))
    values = {name: policy.get(name) for name in THRESHOLD_FIELDS}
    configured = status == "approved" and all(_finite_number(value) for value in values.values())
    if status == "approved" and not configured:
        missing = [name for name, value in values.items() if not _finite_number(value)]
        raise ValueError(f"Approved performance threshold policy is incomplete: {missing}")
    if configured:
        out_of_range = [
            name for name, value in values.items() if not 0 <= float(value) <= 1
        ]
        if out_of_range:
            raise ValueError(
                f"Approved performance thresholds must be between 0 and 1: {out_of_range}"
            )
    normalized = {
        "status": status,
        **{name: float(value) if _finite_number(value) else None for name, value in values.items()},
    }
    kwargs = {
        name: float(value) if configured and _finite_number(value) else None
        for name, value in values.items()
    }
    return normalized, kwargs, configured


def _fairness_policy(raw: object) -> dict[str, Any]:
    policy = raw if isinstance(raw, dict) else {}
    normalized = {
        "status": str(policy.get("status", "not_configured")),
        "min_group_size": policy.get("min_group_size"),
        "max_equal_opportunity_gap": policy.get("max_equal_opportunity_gap"),
        "max_false_positive_rate_gap": policy.get("max_false_positive_rate_gap"),
        "max_selection_rate_gap": policy.get("max_selection_rate_gap"),
    }
    if not isinstance(normalized["min_group_size"], int) or normalized["min_group_size"] < 1:
        raise ValueError("fairness_policy.min_group_size must be a positive integer")
    for name in (
        "max_equal_opportunity_gap",
        "max_false_positive_rate_gap",
        "max_selection_rate_gap",
    ):
        value = normalized[name]
        if not _finite_number(value) or not 0 <= float(value) <= 1:
            raise ValueError(f"fairness_policy.{name} must be between 0 and 1")
        normalized[name] = float(value)
    return normalized


def _assessment_kwargs(
    thresholds: dict[str, float | None],
    fairness: dict[str, Any],
) -> dict[str, Any]:
    return {
        **thresholds,
        "require_fairness": True,
        "min_fairness_group_size": fairness["min_group_size"],
        "max_equal_opportunity_gap": fairness["max_equal_opportunity_gap"],
        "max_false_positive_rate_gap": fairness["max_false_positive_rate_gap"],
        "max_selection_rate_gap": fairness["max_selection_rate_gap"],
    }


def _release_blockers(
    structural: dict[str, Any],
    formal: dict[str, Any],
    *,
    thresholds_configured: bool,
    fairness_policy_approved: bool,
    expected_evidence_type: str,
) -> list[str]:
    blockers: list[str] = []
    if not structural.get("passed"):
        blockers.append("metric_structure_or_integrity_failed")
    if not formal.get("passed"):
        blockers.append("formal_quality_gate_failed")
    if not thresholds_configured:
        blockers.append("approved_performance_thresholds_missing")
    if not fairness_policy_approved:
        blockers.append("approved_fairness_policy_missing")
    if not formal.get("fairness_gate_passed"):
        blockers.append("fairness_gate_failed")
    if formal.get("evidence_type") != expected_evidence_type:
        blockers.append("evidence_classification_mismatch")
    if formal.get("evidence_type") != "prospective_institutional_validation":
        blockers.append("prospective_institutional_validation_missing")
    if formal.get("deployment_claim") != "prospective_validated":
        blockers.append("prospective_deployment_claim_missing")
    if not formal.get("intervention_policy_configured"):
        blockers.append("intervention_policy_not_configured")
    if not formal.get("deployment_eligible"):
        blockers.append("deployment_eligibility_not_established")
    return blockers


def build_track_assessment(
    track_name: str,
    track_config: dict[str, Any],
    fairness: dict[str, Any],
    *,
    repo_root: Path,
) -> dict[str, Any]:
    """Build a complete, evidence-preserving assessment for one model track."""

    raw_metrics_path = Path(str(track_config["metrics"]))
    metrics_path = raw_metrics_path if raw_metrics_path.is_absolute() else repo_root / raw_metrics_path
    metrics = _read_metrics(metrics_path)
    threshold_policy, threshold_kwargs, thresholds_configured = _threshold_policy(
        track_config.get("performance_thresholds")
    )
    structural = assess_model_quality(metrics)
    formal = assess_model_quality(metrics, **_assessment_kwargs(threshold_kwargs, fairness))
    expected_evidence_type = str(track_config.get("expected_evidence_type", "unknown"))
    blockers = _release_blockers(
        structural,
        formal,
        thresholds_configured=thresholds_configured,
        fairness_policy_approved=fairness["status"] == "approved",
        expected_evidence_type=expected_evidence_type,
    )
    release_ready = not blockers
    return {
        "schema_version": 1,
        "track": track_name,
        "assessment_executed": True,
        "metrics_artifact": raw_metrics_path.as_posix(),
        "metrics_sha256": _sha256(metrics_path),
        "expected_evidence_type": expected_evidence_type,
        "threshold_policy": threshold_policy,
        "fairness_policy": fairness,
        "structural_quality": structural,
        "formal_quality": formal,
        "release_decision": {
            "status": "approved" if release_ready else "blocked",
            "release_ready": release_ready,
            "blockers": blockers,
        },
    }


def run_model_quality_suite(config_path: str | Path, output_dir: str | Path) -> dict[str, Any]:
    """Execute every configured assessment and write deterministic JSON evidence."""

    config_file = Path(config_path).resolve()
    config = _read_mapping(config_file)
    if config.get("schema_version") != 1:
        raise ValueError("Unsupported model-quality policy schema_version")
    repo_root = config_file.parent.parent
    fairness = _fairness_policy(config.get("fairness_policy"))
    tracks = config.get("tracks")
    if not isinstance(tracks, dict) or not tracks:
        raise ValueError("Model-quality policy must configure at least one track")

    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    assessments: dict[str, Any] = {}
    for track_name, raw_track_config in tracks.items():
        if not isinstance(raw_track_config, dict):
            raise ValueError(f"Track configuration must be a mapping: {track_name}")
        output_name = str(raw_track_config.get("output", f"{track_name}.json"))
        if Path(output_name).name != output_name or not output_name.endswith(".json"):
            raise ValueError(f"Track output must be a JSON filename: {output_name}")
        assessment = build_track_assessment(
            str(track_name),
            raw_track_config,
            fairness,
            repo_root=repo_root,
        )
        (destination / output_name).write_text(
            json.dumps(assessment, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        assessments[str(track_name)] = assessment

    summary_tracks = {
        name: {
            "assessment_executed": report["assessment_executed"],
            "structural_quality_passed": bool(report["structural_quality"]["passed"]),
            "formal_quality_passed": bool(report["formal_quality"]["passed"]),
            "fairness_gate_passed": bool(report["formal_quality"]["fairness_gate_passed"]),
            "performance_thresholds_configured": report["threshold_policy"]["status"] == "approved",
            "fairness_policy_approved": report["fairness_policy"]["status"] == "approved",
            "deployment_eligible": bool(report["formal_quality"]["deployment_eligible"]),
            "release_decision": report["release_decision"]["status"],
            "release_blockers": report["release_decision"]["blockers"],
        }
        for name, report in assessments.items()
    }
    release_ready = bool(summary_tracks) and all(
        item["release_decision"] == "approved" for item in summary_tracks.values()
    )
    summary = {
        "schema_version": 1,
        "assessment_executed": True,
        "track_count": len(summary_tracks),
        "all_structural_quality_passed": all(
            item["structural_quality_passed"] for item in summary_tracks.values()
        ),
        "all_formal_quality_passed": all(
            item["formal_quality_passed"] for item in summary_tracks.values()
        ),
        "release_ready": release_ready,
        "release_decision": "approved" if release_ready else "blocked",
        "tracks": summary_tracks,
    }
    (destination / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/model-quality.yaml"))
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("artifacts/validation/model_quality"),
    )
    parser.add_argument(
        "--require-release-ready",
        action="store_true",
        help="Exit non-zero after writing reports unless every track is release-ready",
    )
    args = parser.parse_args()
    summary = run_model_quality_suite(args.config, args.output_dir)
    print(json.dumps(summary, indent=2, sort_keys=True))
    if args.require_release_ready and not summary["release_ready"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
