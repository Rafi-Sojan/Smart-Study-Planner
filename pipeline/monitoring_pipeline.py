"""Run privacy-preserving schema and drift checks for feature snapshots."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from src.monitoring.drift import assess_drift


def run_monitoring(
    reference_path: str | Path,
    current_path: str | Path,
    output_path: str | Path | None = None,
) -> dict[str, object]:
    """Compare two CSV feature snapshots without writing row-level data."""

    reference = pd.read_csv(reference_path)
    current = pd.read_csv(current_path)
    report = assess_drift(reference, current)
    report["reference_rows"] = int(len(reference))
    report["current_rows"] = int(len(current))
    if output_path is not None:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Check feature snapshot drift")
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--current", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    print(json.dumps(run_monitoring(args.reference, args.current, args.output), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
