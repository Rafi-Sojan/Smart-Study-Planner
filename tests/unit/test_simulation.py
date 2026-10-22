from pathlib import Path

import pandas as pd

from src.simulation.simulator import SimulationConfig, generate_dataset


def test_simulation_is_reproducible_and_covers_profiles(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    config = SimulationConfig(output_dir=first, seed=123, students=8, terms=1, weeks_per_term=8)
    first_counts = generate_dataset(config)
    second_counts = generate_dataset(config.__class__(**{**config.__dict__, "output_dir": second}))

    assert first_counts == second_counts
    assert (first / "manifest.json").exists()
    assert pd.read_csv(first / "students.csv").shape == (8, 8)
    assert pd.read_csv(first / "students.csv").equals(pd.read_csv(second / "students.csv"))
    assert pd.read_csv(first / "outcomes.csv").shape[0] > 0
    assert pd.read_csv(first / "study_sessions.csv").shape[0] > 0


def test_simulation_requires_explicit_overwrite(tmp_path: Path) -> None:
    output = tmp_path / "generated"
    config = SimulationConfig(output_dir=output, students=4, terms=1, weeks_per_term=8)
    generate_dataset(config)

    try:
        generate_dataset(config)
    except FileExistsError:
        pass
    else:
        raise AssertionError("Expected existing CSV output to require explicit overwrite")

    generate_dataset(config.__class__(**{**config.__dict__, "overwrite": True}))


def test_simulation_requires_enough_students_for_profile_coverage(tmp_path: Path) -> None:
    config = SimulationConfig(output_dir=tmp_path / "generated", students=3)

    try:
        generate_dataset(config)
    except ValueError as error:
        assert "at least 4" in str(error)
    else:
        raise AssertionError("Expected a validation error for fewer than four students")
