import pandas as pd
import pytest

from src.data.validation import validate_oulad_tables
from src.monitoring.drift import assess_drift


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
