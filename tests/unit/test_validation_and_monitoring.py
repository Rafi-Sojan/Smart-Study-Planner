import pandas as pd
import pytest

from src.data.validation import validate_oulad_tables
from src.data.synthetic_validation import validate_synthetic_dataset
from src.monitoring.drift import assess_drift
from src.models.evaluate import calibration_summary
from src.models.policy import intervention_policy_summary


def test_oulad_validation_rejects_out_of_range_scores() -> None:
    tables = {
        "studentInfo": pd.DataFrame(
            {
                "id_student": [1],
                "code_presentation": ["2013J"],
                "final_result": ["Pass"],
            }
        ),
        "studentAssessment": pd.DataFrame({"score": [101]}),
    }
    with pytest.raises(ValueError, match="score_out_of_range"):
        validate_oulad_tables(tables)


def test_drift_report_does_not_include_row_values() -> None:
    reference = pd.DataFrame({"x": [1, 2, 3], "category": ["a", "a", "b"]})
    current = pd.DataFrame({"x": [100, 101, 102], "category": ["c", "c", "c"]})
    report = assess_drift(reference, current)
    serialized = str(report)
    assert "100" not in serialized
    assert report["status"] == "warning"


def test_calibration_summary_reports_bounded_error_and_bins() -> None:
    report = calibration_summary(
        pd.Series([0, 0, 1, 1]),
        [0.1, 0.2, 0.8, 0.9],
        n_bins=4,
    )

    assert 0 <= report["expected_calibration_error"] <= 1
    assert len(report["bins"]) == 4
    assert sum(row["count"] for row in report["bins"]) == 4


def test_intervention_policy_requires_reviewed_inputs() -> None:
    unconfigured = intervention_policy_summary(pd.Series([0, 1]), [0.2, 0.8])
    assert unconfigured["status"] == "not_configured"
    configured = intervention_policy_summary(
        pd.Series([0, 1, 1, 0]),
        [0.1, 0.6, 0.7, 0.9],
        max_alert_rate=0.5,
    )
    assert configured["status"] == "configured"
    assert configured["selected_threshold"] is not None


def test_synthetic_validation_reports_external_validity_as_unassessed(tmp_path) -> None:
    (tmp_path / "manifest.json").write_text(
        '{"synthetic_record_flag": true, "tables": {}}',
        encoding="utf-8",
    )

    report = validate_synthetic_dataset(tmp_path)

    assert report["status"] == "error"
    assert report["external_validity"] == "not_assessed"
