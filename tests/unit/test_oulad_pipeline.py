from pathlib import Path

import pandas as pd
import pytest

from pipeline.training_pipeline import run_training
from src.data.cleaner import clean_student_assessment, write_clean_tables
from src.data.loader import load_clean_table, load_oulad_tables
from src.features.feature_engineering import build_oulad_features


def make_tables() -> dict[str, pd.DataFrame]:
    students = list(range(100, 112))
    info = pd.DataFrame(
        {
            "id_student": students,
            "code_module": ["AAA"] * len(students),
            "code_presentation": ["2013J"] * len(students),
            "gender": ["M", "F"] * 6,
            "highest_education": ["A Level"] * len(students),
            "final_result": ["Pass"] * 6 + ["Fail"] * 6,
            "num_of_prev_attempts": [0] * len(students),
            "studied_credits": [60] * len(students),
        }
    )
    assessment = pd.DataFrame(
        {
            "id_assessment": [1, 2],
            "code_module": ["AAA", "AAA"],
            "code_presentation": ["2013J", "2013J"],
            "assessment_type": ["TMA", "Exam"],
            "date": [20, 100],
            "weight": [50.0, 50.0],
        }
    )
    student_assessment = pd.DataFrame(
        {
            "id_student": students * 2,
            "id_assessment": [1] * len(students) + [2] * len(students),
            "date_submitted": [18] * len(students) + [98] * len(students),
            "is_banked": [0] * (len(students) * 2),
            "score": [80.0] * 6 + [40.0] * 6 + [80.0] * 6 + [40.0] * 6,
        }
    )
    registration = pd.DataFrame(
        {
            "id_student": students,
            "code_module": ["AAA"] * len(students),
            "code_presentation": ["2013J"] * len(students),
            "date_registration": [-10] * len(students),
            "date_unregistration": [None] * len(students),
        }
    )
    return {
        "studentInfo": info,
        "assessments": assessment,
        "studentAssessment": student_assessment,
        "studentRegistration": registration,
    }


def write_raw_tables(root: Path, tables: dict[str, pd.DataFrame]) -> None:
    root.mkdir(parents=True, exist_ok=True)
    for name, frame in tables.items():
        frame.to_csv(root / f"{name}.csv", index=False)


def test_loader_reports_missing_required_oulad_file(tmp_path: Path) -> None:
    tables = make_tables()
    write_raw_tables(tmp_path, {name: tables[name] for name in ("studentInfo", "assessments")})

    with pytest.raises(FileNotFoundError, match="studentAssessment.csv"):
        load_oulad_tables(tmp_path)


def test_cleaner_does_not_turn_invalid_or_missing_scores_into_scores() -> None:
    frame = pd.DataFrame(
        {
            "id_student": [1, 2, 3],
            "id_assessment": [10, 10, 10],
            "score": [75, 101, None],
        }
    )

    cleaned = clean_student_assessment(frame)

    assert cleaned["score"].iloc[0] == 75
    assert pd.isna(cleaned["score"].iloc[1])
    assert pd.isna(cleaned["score"].iloc[2])


def test_feature_builder_creates_one_labeled_enrollment_row() -> None:
    features = build_oulad_features(make_tables())

    assert len(features) == 12
    assert features["target_risk"].tolist() == [0] * 6 + [1] * 6
    assert features.loc[0, "assessment_count"] == 2
    assert features.loc[0, "assessment_score_mean"] == 80
    assert features.loc[0, "date_registration"] == -10


def test_feature_builder_handles_oulad_activity_columns() -> None:
    tables = make_tables()
    tables["vle"] = pd.DataFrame(
        {
            "id_site": [501],
            "code_module": ["AAA"],
            "code_presentation": ["2013J"],
        }
    )
    tables["studentVle"] = pd.DataFrame(
        {
            "code_module": ["AAA", "AAA"],
            "code_presentation": ["2013J", "2013J"],
            "id_student": [100, 100],
            "id_site": [501, 501],
            "date": [1, 2],
            "sum_click": [3, 4],
        }
    )

    features = build_oulad_features(tables)

    assert features.loc[0, "vle_clicks"] == 7
    assert features.loc[0, "vle_active_days"] == 2


def test_clean_table_round_trip_writes_manifest(tmp_path: Path) -> None:
    cleaned = make_tables()
    manifest = write_clean_tables(cleaned, tmp_path)

    assert manifest.is_file()
    loaded = load_clean_table("studentInfo", tmp_path)
    assert len(loaded) == 12
    assert loaded.loc[0, "final_result"] == "Pass"


def test_training_pipeline_runs_on_explicit_fixture_data(tmp_path: Path) -> None:
    raw_dir = tmp_path / "raw"
    write_raw_tables(raw_dir, make_tables())
    metrics_path = tmp_path / "metrics.json"
    model_path = tmp_path / "baseline.pkl"

    metrics = run_training(raw_dir, metrics_path, model_path)

    assert metrics["n_samples"] == 12
    assert metrics["n_train"] == 9
    assert metrics["n_test"] == 3
    assert metrics["best_model"] in {
        "logistic_regression",
        "random_forest",
        "extra_trees",
        "hist_gradient_boosting",
    }
    assert set(metrics["models"]) == {
        "logistic_regression",
        "random_forest",
        "extra_trees",
        "hist_gradient_boosting",
    }
    assert metrics_path.is_file()
    assert model_path.is_file()
