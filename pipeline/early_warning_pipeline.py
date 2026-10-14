"""Run leakage-aware early-warning evaluations at course-relative cutoffs."""

import argparse
import json
from pathlib import Path
from typing import Any, Iterable

from src.data.cleaner import clean_oulad_tables
from src.data.loader import load_oulad_tables
from src.features.feature_engineering import build_oulad_features
from src.models.baseline import split_time_aware_data, train_time_aware_baselines


DEFAULT_CUTOFFS = (30, 60, 90)


def _ordered(values: Iterable[object]) -> list[str]:
    return sorted({str(value) for value in values}, key=lambda value: (value[:4], value[4:]))


def run_early_warning(
    data_dir: str | Path,
    metrics_output: str | Path | None = None,
    cutoffs_days: Iterable[int] = DEFAULT_CUTOFFS,
    test_presentations: Iterable[str] | None = None,
) -> dict[str, Any]:
    """Evaluate full-course labels using only observations before each cutoff."""

    raw_tables = load_oulad_tables(data_dir)
    cleaned_tables = clean_oulad_tables(raw_tables)
    cutoffs = sorted({int(cutoff) for cutoff in cutoffs_days})
    if not cutoffs or any(cutoff < 0 for cutoff in cutoffs):
        raise ValueError("cutoffs_days must contain non-negative integers")

    evaluations: dict[str, Any] = {}
    for cutoff in cutoffs:
        features = build_oulad_features(
            cleaned_tables,
            clean=False,
            cutoff_days=cutoff,
        )
        best_name, _, model_results = train_time_aware_baselines(
            features,
            test_presentations=test_presentations,
        )
        train_features, test_features, _, _ = split_time_aware_data(
            features,
            test_presentations=test_presentations,
        )
        evaluations[str(cutoff)] = {
            "cutoff_days": cutoff,
            "best_model": best_name,
            "train_presentations": _ordered(train_features["code_presentation"]),
            "test_presentations": _ordered(test_features["code_presentation"]),
            "models": model_results,
        }

    metrics: dict[str, Any] = {
        "task": "early_warning_enrollment_risk_classification",
        "target": "Fail/Withdrawn = 1; Pass/Distinction = 0",
        "evaluation": "time-aware course-presentation holdout",
        "cutoffs_days": cutoffs,
        "evaluations": evaluations,
    }
    if metrics_output is not None:
        path = Path(metrics_output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(metrics, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser(description="Run leakage-aware OULAD early-warning evaluation")
    parser.add_argument("--data-dir", type=Path, default=Path("data/processed/oulad"))
    parser.add_argument(
        "--metrics-output",
        type=Path,
        default=Path("models/metrics/early_warning_metrics.json"),
    )
    parser.add_argument("--cutoffs-days", type=int, nargs="+", default=list(DEFAULT_CUTOFFS))
    parser.add_argument("--test-presentations", nargs="+", default=None)
    args = parser.parse_args()
    metrics = run_early_warning(
        args.data_dir,
        metrics_output=args.metrics_output,
        cutoffs_days=args.cutoffs_days,
        test_presentations=args.test_presentations,
    )
    print(json.dumps(metrics, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
