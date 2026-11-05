"""Run privacy-preserving schema and drift checks for feature snapshots."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from src.monitoring.drift import assess_drift
from src.monitoring.prometheus_exporter import push_drift_metrics


def run_monitoring(
    reference_path: str | Path,
    current_path: str | Path,
    output_path: str | Path | None = None,
    pushgateway_url: str | None = None,
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
    push_drift_metrics(report, pushgateway_url=pushgateway_url)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Check feature snapshot drift")
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--current", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--pushgateway-url", default=None)
    parser.add_argument("--fail-on-warning", action="store_true")
    args = parser.parse_args()
    report = run_monitoring(
        args.reference,
        args.current,
        args.output,
        pushgateway_url=args.pushgateway_url,
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    if args.fail_on_warning and report["status"] != "ok":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
