from src.risk.model_risk import assess_model_quality


def _metrics() -> dict:
    return {
        "best_model": "logistic_regression",
        "target": "risk",
        "n_samples": 100,
        "n_train": 70,
        "n_test": 30,
        "evidence_type": "retrospective_historical_benchmark",
        "deployment_claim": "not_prospective_or_causal_evidence",
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
                "intervention_policy": {"status": "not_configured"},
            }
        },
    }


def test_quality_report_distinguishes_structural_pass_from_deployment_eligibility() -> None:
    report = assess_model_quality(_metrics(), min_pr_auc=0.7)
    assert report["passed"] is True
    assert report["deployment_eligible"] is False


def test_quality_gate_rejects_metric_threshold_failure() -> None:
    report = assess_model_quality(_metrics(), min_pr_auc=0.9)
    assert report["passed"] is False
    assert any(check["name"] == "pr_auc_gate" and not check["passed"] for check in report["checks"])


def test_quality_gate_rejects_missing_confusion_matrix() -> None:
    metrics = _metrics()
    del metrics["models"]["logistic_regression"]["confusion_matrix"]
    report = assess_model_quality(metrics)
    assert report["passed"] is False


def test_quality_gate_checks_validation_threshold_operating_point() -> None:
    metrics = _metrics()
    metrics["models"]["logistic_regression"]["test_at_validation_threshold"] = {
        "recall": 0.4,
        "confusion_matrix": [[10, 5], [6, 4]],
    }
    report = assess_model_quality(metrics, min_operating_point_recall=0.5)
    assert report["passed"] is False
    assert any(
        check["name"] == "operating_point_recall_gate" and not check["passed"]
        for check in report["checks"]
    )


def test_quality_gate_checks_each_cutoff_in_nested_evaluation() -> None:
    metrics = {
        "target": "risk",
        "evaluations": {
            "30": {
                "best_model": "logistic_regression",
                "n_samples": 100,
                "n_train": 70,
                "n_test": 30,
                "models": _metrics()["models"],
            }
        },
    }
    report = assess_model_quality(metrics)
    assert report["passed"] is True
    assert report["deployment_eligible"] is False
    assert report["cutoffs"]["30"]["selected_model"] == "logistic_regression"
