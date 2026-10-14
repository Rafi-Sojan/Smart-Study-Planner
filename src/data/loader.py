"""Load OULAD CSV tables with explicit input validation."""

from pathlib import Path
from typing import Iterable

import pandas as pd


CORE_FILES = (
    "studentInfo.csv",
    "assessments.csv",
    "studentAssessment.csv",
)
OPTIONAL_FILES = (
    "courses.csv",
    "studentRegistration.csv",
    "vle.csv",
    "studentVle.csv",
)


def validate_oulad_directory(
    data_dir: str | Path,
    required_files: Iterable[str] = CORE_FILES,
) -> dict[str, Path]:
    """Return required file paths or raise an actionable error.

    The loader never downloads data and never creates placeholder rows. The
    caller must obtain the OULAD release separately and place its CSV files in
    ``data_dir``.
    """

    root = Path(data_dir)
    if not root.is_dir():
        raise FileNotFoundError(f"OULAD directory does not exist: {root}")

    paths = {name: root / name for name in required_files}
    missing = [name for name, path in paths.items() if not path.is_file()]
    if missing:
        names = ", ".join(missing)
        raise FileNotFoundError(
            f"Missing required OULAD file(s) in {root}: {names}. "
            "Download the dataset and place the CSV files there."
        )
    return paths


def load_oulad_tables(
    data_dir: str | Path,
    required_files: Iterable[str] = CORE_FILES,
) -> dict[str, pd.DataFrame]:
    """Load required and available optional OULAD tables from CSV files."""

    root = Path(data_dir)
    required_paths = validate_oulad_directory(root, required_files)
    names = list(required_paths)
    for name in OPTIONAL_FILES:
        if name not in required_paths and (root / name).is_file():
            names.append(name)

    return {
        Path(name).stem: pd.read_csv(root / name, low_memory=False)
        for name in names
    }


def load_clean_table(table_name: str, data_dir: str | Path) -> pd.DataFrame:
    """Load a cleaned table written by :func:`write_clean_tables`.

    CSV is the default portable format. Parquet is accepted when present so
    this helper remains compatible with future storage changes.
    """

    root = Path(data_dir)
    for suffix, reader in ((".csv", pd.read_csv), (".parquet", pd.read_parquet)):
        path = root / f"{table_name}{suffix}"
        if path.is_file():
            return reader(path)
    raise FileNotFoundError(
        f"No cleaned table found for {table_name!r} in {root}; expected "
        f"{table_name}.csv or {table_name}.parquet"
    )
