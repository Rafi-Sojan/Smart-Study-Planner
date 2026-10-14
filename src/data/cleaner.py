"""Deterministic, non-imputing cleaning for OULAD tables."""

import argparse
import json
from pathlib import Path
from typing import Callable

import pandas as pd

from src.data.loader import load_oulad_tables


VALID_OUTCOMES = {"Distinction", "Pass", "Fail", "Withdrawn"}


def _require_columns(frame: pd.DataFrame, required: set[str], table: str) -> None:
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise ValueError(f"{table} is missing required column(s): {', '.join(missing)}")


def _copy(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    result.columns = [str(column).strip() for column in result.columns]
    return result


def clean_student_info(frame: pd.DataFrame) -> pd.DataFrame:
    result = _copy(frame)
    _require_columns(result, {"id_student", "code_presentation", "final_result"}, "studentInfo")
    for column in ("id_student", "num_of_prev_attempts", "studied_credits"):
        if column in result:
            result[column] = pd.to_numeric(result[column], errors="coerce")
    result["final_result"] = result["final_result"].astype("string").str.strip()
    invalid = result["final_result"].notna() & ~result["final_result"].isin(VALID_OUTCOMES)
    result.loc[invalid, "final_result"] = pd.NA
    return result


def clean_assessments(frame: pd.DataFrame) -> pd.DataFrame:
    result = _copy(frame)
    _require_columns(result, {"id_assessment", "code_presentation", "weight"}, "assessments")
    result["id_assessment"] = pd.to_numeric(result["id_assessment"], errors="coerce")
    result["weight"] = pd.to_numeric(result["weight"], errors="coerce")
    if "date" in result:
        result["date"] = pd.to_numeric(result["date"], errors="coerce")
    return result.dropna(subset=["id_assessment"]).drop_duplicates("id_assessment")


def clean_student_assessment(frame: pd.DataFrame) -> pd.DataFrame:
    result = _copy(frame)
    _require_columns(result, {"id_student", "id_assessment", "score"}, "studentAssessment")
    for column in ("id_student", "id_assessment", "date_submitted", "is_banked", "score"):
        if column in result:
            result[column] = pd.to_numeric(result[column], errors="coerce")
    result = result.dropna(subset=["id_student", "id_assessment"])
    invalid_scores = result["score"].notna() & ~result["score"].between(0, 100)
    result.loc[invalid_scores, "score"] = pd.NA
    return result


def clean_student_registration(frame: pd.DataFrame) -> pd.DataFrame:
    result = _copy(frame)
    _require_columns(result, {"id_student", "code_presentation"}, "studentRegistration")
    for column in ("id_student", "date_registration", "date_unregistration"):
        if column in result:
            result[column] = pd.to_numeric(result[column], errors="coerce")
    return result


def clean_student_vle(frame: pd.DataFrame) -> pd.DataFrame:
    result = _copy(frame)
    _require_columns(result, {"id_student", "id_site", "date", "sum_click"}, "studentVle")
    for column in ("id_student", "id_site", "date", "sum_click"):
        result[column] = pd.to_numeric(result[column], errors="coerce")
    return result.dropna(subset=["id_student", "id_site", "sum_click"])


def clean_vle(frame: pd.DataFrame) -> pd.DataFrame:
    result = _copy(frame)
    _require_columns(result, {"id_site", "code_presentation"}, "vle")
    result["id_site"] = pd.to_numeric(result["id_site"], errors="coerce")
    return result.dropna(subset=["id_site"]).drop_duplicates("id_site")


def clean_oulad_tables(tables: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """Clean tables without filling unknown values with fabricated data."""

    cleaners: dict[str, Callable[[pd.DataFrame], pd.DataFrame]] = {
        "studentInfo": clean_student_info,
        "assessments": clean_assessments,
        "studentAssessment": clean_student_assessment,
        "studentRegistration": clean_student_registration,
        "studentVle": clean_student_vle,
        "vle": clean_vle,
    }
    return {
        name: cleaners.get(name, _copy)(frame)
        for name, frame in tables.items()
    }


def write_clean_tables(
    tables: dict[str, pd.DataFrame],
    output_dir: str | Path,
    raw_row_counts: dict[str, int] | None = None,
) -> Path:
    """Write cleaned CSV tables and a small manifest; return manifest path."""

    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    manifest_tables = {}
    for name, frame in tables.items():
        frame.to_csv(root / f"{name}.csv", index=False)
        manifest_tables[name] = {
            "raw_rows": (raw_row_counts or {}).get(name, len(frame)),
            "clean_rows": len(frame),
        }
    manifest_path = root / "manifest.json"
    manifest_path.write_text(
        json.dumps({"tables": manifest_tables}, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Clean OULAD CSV tables")
    parser.add_argument("--input-dir", type=Path, default=Path("data/raw/oulad"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/processed/oulad"))
    args = parser.parse_args()

    raw_tables = load_oulad_tables(args.input_dir)
    cleaned_tables = clean_oulad_tables(raw_tables)
    manifest = write_clean_tables(
        cleaned_tables,
        args.output_dir,
        raw_row_counts={name: len(frame) for name, frame in raw_tables.items()},
    )
    print(f"Wrote {len(cleaned_tables)} cleaned OULAD table(s) and {manifest}")


if __name__ == "__main__":
    main()
