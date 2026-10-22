"""Integrity checks for the synthetic planner dataset.

These checks establish generator and relational integrity only. They do not
establish that the simulated distributions represent a real university.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd


REQUIRED_TABLES = (
    "students",
    "academic_terms",
    "courses",
    "course_offerings",
    "enrollments",
    "outcomes",
)
PRIMARY_KEYS = {
    "students": "student_id",
    "academic_terms": "term_id",
    "courses": "course_id",
    "course_offerings": "offering_id",
    "enrollments": "enrollment_id",
    "outcomes": "outcome_id",
}
FOREIGN_KEYS = (
    ("students", "program_id", "programs", "program_id"),
    ("academic_terms", "university_id", "universities", "university_id"),
    ("courses", "program_id", "programs", "program_id"),
    ("course_offerings", "course_id", "courses", "course_id"),
    ("course_offerings", "term_id", "academic_terms", "term_id"),
    ("course_offerings", "department_id", "departments", "department_id"),
    ("enrollments", "student_id", "students", "student_id"),
    ("enrollments", "offering_id", "course_offerings", "offering_id"),
    ("outcomes", "student_id", "students", "student_id"),
    ("outcomes", "offering_id", "course_offerings", "offering_id"),
)


def _load_tables(data_dir: Path) -> dict[str, pd.DataFrame]:
    return {
        path.stem: pd.read_csv(path)
        for path in sorted(data_dir.glob("*.csv"))
    }


def validate_synthetic_dataset(data_dir: str | Path) -> dict[str, Any]:
    """Return a deterministic integrity and provenance report for generated data."""

    root = Path(data_dir)
    manifest_path = root / "manifest.json"
    errors: list[str] = []
    warnings: list[str] = []
    checks: list[dict[str, Any]] = []
    if not root.is_dir():
        return {
            "status": "error",
            "errors": [f"data directory does not exist: {root}"],
            "warnings": [],
            "external_validity": "not_assessed",
        }
    if not manifest_path.is_file():
        errors.append("manifest.json is missing")
        manifest: dict[str, Any] = {}
    else:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("synthetic_record_flag") is not True:
            errors.append("manifest synthetic_record_flag must be true")

    tables = _load_tables(root)
    for table_name in REQUIRED_TABLES:
        if table_name not in tables:
            errors.append(f"missing required table: {table_name}.csv")

    manifest_counts = manifest.get("tables", {})
    for table_name, frame in tables.items():
        expected = manifest_counts.get(table_name)
        matches_manifest = expected is None or int(expected) == len(frame)
        checks.append(
            {
                "check": "manifest_row_count",
                "table": table_name,
                "passed": bool(matches_manifest),
                "observed_rows": int(len(frame)),
                "manifest_rows": expected,
            }
        )
        if not matches_manifest:
            errors.append(f"manifest row count mismatch: {table_name}")

    for table_name, key in PRIMARY_KEYS.items():
        frame = tables.get(table_name)
        if frame is None or key not in frame:
            errors.append(f"missing primary key column: {table_name}.{key}")
            continue
        passed = bool(frame[key].notna().all() and frame[key].is_unique)
        checks.append({"check": "primary_key_integrity", "table": table_name, "column": key, "passed": passed})
        if not passed:
            errors.append(f"primary key integrity failure: {table_name}.{key}")

    for child_table, child_column, parent_table, parent_column in FOREIGN_KEYS:
        child = tables.get(child_table)
        parent = tables.get(parent_table)
        if child is None or parent is None or child_column not in child or parent_column not in parent:
            errors.append(f"missing foreign-key column: {child_table}.{child_column}")
            continue
        parent_values = set(parent[parent_column].dropna())
        orphan_count = int((~child[child_column].isin(parent_values)).sum())
        passed = orphan_count == 0
        checks.append(
            {
                "check": "foreign_key_integrity",
                "child": f"{child_table}.{child_column}",
                "parent": f"{parent_table}.{parent_column}",
                "passed": passed,
                "orphan_count": orphan_count,
            }
        )
        if not passed:
            errors.append(f"foreign-key integrity failure: {child_table}.{child_column}")

    if manifest.get("limitations"):
        warnings.extend(str(item) for item in manifest["limitations"])
    warnings.append("External validity against a real university population was not assessed.")
    return {
        "status": "error" if errors else "passed",
        "data_source": "synthetic_indian_university_planner",
        "external_validity": "not_assessed",
        "errors": errors,
        "warnings": warnings,
        "checks": checks,
        "table_row_counts": {name: int(len(frame)) for name, frame in tables.items()},
        "manifest_configuration": manifest.get("configuration", {}),
    }


def write_validation_report(data_dir: str | Path, output: str | Path) -> dict[str, Any]:
    """Validate generated records and write a JSON report without row-level data."""

    report = validate_synthetic_dataset(data_dir)
    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def main() -> None:
    """Run synthetic integrity validation from the command line."""

    import argparse

    parser = argparse.ArgumentParser(description="Validate the synthetic planner dataset")
    parser.add_argument("--data-dir", type=Path, default=Path("data/raw/synthetic"))
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("models/validation/synthetic_data_validation.json"),
    )
    args = parser.parse_args()
    report = write_validation_report(args.data_dir, args.output)
    print(json.dumps(report, indent=2, sort_keys=True))
    if report["status"] != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
