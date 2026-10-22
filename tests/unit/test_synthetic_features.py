from pathlib import Path

from src.features.synthetic_features import build_synthetic_features, load_synthetic_tables
from src.simulation.simulator import SimulationConfig, generate_dataset


def test_synthetic_features_are_enrollment_level_and_keep_label(tmp_path: Path) -> None:
    output = tmp_path / "synthetic"
    generate_dataset(SimulationConfig(output_dir=output, seed=7, students=8, terms=1, weeks_per_term=8))
    tables = load_synthetic_tables(output)

    features = build_synthetic_features(tables, cutoff_days=30)

    assert len(features) == len(tables["enrollments"])
    assert features["enrollment_id"].is_unique
    assert set(features["risk_label"].unique()) <= {0, 1}
    assert features["observation_cutoff_days"].eq(30).all()
    assert "result_status" not in features.columns
    assert "final_grade" not in features.columns
    assert "prior_cumulative_gpa" in features.columns
    assert "unmet_prerequisite_count" in features.columns
    assert features.loc[features["term_number"] == 1, "prior_cumulative_gpa"].isna().all()

