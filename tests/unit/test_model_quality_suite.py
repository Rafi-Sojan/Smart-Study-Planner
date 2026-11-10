import json
from pathlib import Path

import pytest
import yaml

from pipeline.model_quality_suite import build_track_assessment, run_model_quality_suite


FAIRNESS_POLICY = {
    "status": "engineering_review_default_not_production_approval",
    "min_group_size": 30,
    "max_equal_opportunity_gap": 0.20,
    "max_false_positive_rate_gap": 0.20,
    "max_selection_rate_gap": 0.20,
}

APPROVED_FAIRNESS_POLICY = {
    **FAIRNESS_POLICY,
    "status": "approved",
}


def _metrics(*, prospective: bool = False) -> dict:
    return {
        "best_model": "logistic_regression",
        "target": "risk",
        "n_samples": 100,
        "n_train": 70,
        "n_test": 30,
        "evidence_type": (
            "prospective_institutional_validation"
            if prospective
            else "retrospective_historical_benchmark"
        ),
        "deployment_claim": (
            "prospective_validated"
            if prospective
            else "not_prospective_or_causal_evidence"
        ),
        "models": {
            "logistic_regression": {
                "accuracy": 0.8,
                "balanced_accuracy": 0.75,
                "f1": 0.7,
                "precision": 0.8,
                "recall": 0.6,
                "roc_auc": 0.85,
                "pr_auc": 0.8,
                "brier_score": 0.15,
                "expected_calibration_error": 0.05,
                "confusion_matrix": [[12, 3], [4, 11]],
                "test_at_validation_threshold": {
                    "recall": 0.6,
                    "confusion_matrix": [[12, 3], [4, 11]],
                },
                "intervention_policy": {
                    "status": "configured" if prospective else "not_configured"
                },
                "fairness_report": {
                    "methodology": {"min_group_size": 30},
                    "summary": {
                        "evaluated_attribute_count": 2,
                        "max_equal_opportunity_gap": 0.10,
                        "max_false_positive_rate_gap": 0.08,
                        "max_selection_rate_gap": 0.12,
                    },
                },
            }
        },
    }


def _write_metrics(root: Path, metrics: dict) -> Path:
    path = root / "artifacts/metrics/metrics.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(metrics), encoding="utf-8")
    return path


def test_assessment_blocks_release_when_thresholds_and_prospective_evidence_are_missing(
    tmp_path: Path,
) -> None:
    _write_metrics(tmp_path, _metrics())
    report = build_track_assessment(
        "historical",
        {
            "metrics": "artifacts/metrics/metrics.json",
            "expected_evidence_type": "retrospective_historical_benchmark",
            "performance_thresholds": {"status": "not_approved"},
        },
        FAIRNESS_POLICY,
        repo_root=tmp_path,
    )

    assert report["assessment_executed"] is True
    assert report["structural_quality"]["passed"] is True
    assert report["formal_quality"]["fairness_gate_passed"] is True
    assert report["release_decision"]["status"] == "blocked"
    assert "approved_performance_thresholds_missing" in report["release_decision"]["blockers"]
    assert "approved_fairness_policy_missing" in report["release_decision"]["blockers"]
    assert "prospective_institutional_validation_missing" in report["release_decision"]["blockers"]


def test_assessment_approves_only_complete_prospective_evidence(tmp_path: Path) -> None:
    _write_metrics(tmp_path, _metrics(prospective=True))
    report = build_track_assessment(
        "prospective",
        {
            "metrics": "artifacts/metrics/metrics.json",
            "expected_evidence_type": "prospective_institutional_validation",
            "performance_thresholds": {
                "status": "approved",
                "min_pr_auc": 0.70,
                "min_balanced_accuracy": 0.70,
                "min_operating_point_recall": 0.50,
                "max_expected_calibration_error": 0.10,
            },
        },
        APPROVED_FAIRNESS_POLICY,
        repo_root=tmp_path,
    )

    assert report["formal_quality"]["passed"] is True
    assert report["formal_quality"]["deployment_eligible"] is True
    assert report["release_decision"] == {
        "status": "approved",
        "release_ready": True,
        "blockers": [],
    }


def test_assessment_rejects_out_of_range_approved_thresholds(tmp_path: Path) -> None:
    _write_metrics(tmp_path, _metrics(prospective=True))

    with pytest.raises(ValueError, match="must be between 0 and 1"):
        build_track_assessment(
            "prospective",
            {
                "metrics": "artifacts/metrics/metrics.json",
                "expected_evidence_type": "prospective_institutional_validation",
                "performance_thresholds": {
                    "status": "approved",
                    "min_pr_auc": 1.1,
                    "min_balanced_accuracy": 0.70,
                    "min_operating_point_recall": 0.50,
                    "max_expected_calibration_error": 0.10,
                },
            },
            APPROVED_FAIRNESS_POLICY,
            repo_root=tmp_path,
        )


def test_suite_writes_deterministic_track_and_summary_reports(tmp_path: Path) -> None:
    _write_metrics(tmp_path, _metrics())
    config_path = tmp_path / "configs/model-quality.yaml"
    config_path.parent.mkdir()
    config_path.write_text(
        yaml.safe_dump(
            {
                "schema_version": 1,
                "fairness_policy": FAIRNESS_POLICY,
                "tracks": {
                    "historical": {
                        "metrics": "artifacts/metrics/metrics.json",
                        "output": "historical.json",
                        "expected_evidence_type": "retrospective_historical_benchmark",
                        "performance_thresholds": {"status": "not_approved"},
                    }
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    output_dir = tmp_path / "artifacts/validation/model_quality"

    summary = run_model_quality_suite(config_path, output_dir)

    assert summary["assessment_executed"] is True
    assert summary["track_count"] == 1
    assert summary["release_decision"] == "blocked"
    assert (output_dir / "historical.json").is_file()
    stored_summary = json.loads((output_dir / "summary.json").read_text(encoding="utf-8"))
    assert stored_summary == summary
