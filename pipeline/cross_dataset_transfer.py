"""Evaluate KU Leuven-trained engagement models on synthetic enrollments."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from pipeline.kuleuven_external_validation import PREDICTOR_COLUMNS, run_external_validation
from src.data.transfer import build_synthetic_transfer_features
from src.models.evaluate import evaluate_at_threshold, evaluate_classifier


def run_cross_dataset_transfer(
    kuleuven_path: str | Path,
    synthetic_path: str | Path,
    cutoffs_days: tuple[int, ...] = (30, 60, 90),
) -> dict[str, Any]:
    """Train on KU Leuven and evaluate on synthetic data without refitting."""

    source_metrics, source_models = run_external_validation(kuleuven_path, cutoffs_days)
    evaluations: dict[str, Any] = {}
    for cutoff in sorted({int(value) for value in cutoffs_days}):
        source_evaluation = source_metrics["evaluations"][str(cutoff)]
        selected_model_name = source_evaluation["best_model"]
        model = source_models[cutoff][selected_model_name]
        synthetic = build_synthetic_transfer_features(synthetic_path, cutoff)
        x_synthetic = synthetic.loc[:, list(PREDICTOR_COLUMNS)]
        y_synthetic = synthetic["target_risk"]
        metrics = evaluate_classifier(model, x_synthetic, y_synthetic)
        source_threshold = source_evaluation["models"][selected_model_name][
            "validation_selected_threshold"
        ]
        metrics["at_source_validation_threshold"] = evaluate_at_threshold(
            y_synthetic,
            model.predict_proba(x_synthetic)[:, 1],
            float(source_threshold),
        )
        metrics.update(
            {
                "source_model": selected_model_name,
                "source_validation_pr_auc": source_evaluation["models"][selected_model_name][
                    "validation_pr_auc"
                ],
                "source_validation_threshold": source_threshold,
                "n_synthetic_rows": int(len(synthetic)),
                "feature_columns": list(PREDICTOR_COLUMNS),
                "target_positive_rate": float(y_synthetic.mean()),
            }
        )
        evaluations[str(cutoff)] = metrics
    return {
        "task": "kuleuven_to_synthetic_cross_dataset_transfer",
        "source_dataset": "KU Leuven Open Data, Private Learners",
        "target_dataset": "synthetic Indian-university planner",
        "evaluation": "source model trained on KU Leuven 1819+1920 and applied unchanged to synthetic enrollments",
        "interpretation": "development transfer stress test; not real-world validation and not evidence that synthetic data is realistic",
        "feature_mapping": {
            "activity_count": "KU Leuven LMS actions; synthetic study-session rows",
            "active_day_count": "distinct observed event dates",
            "content_count": "distinct LMS content; synthetic distinct topic IDs",
            "session_count": "distinct LMS sessions; synthetic distinct study sessions",
            "mean_daily_activity": "activity_count divided by active_day_count",
            "has_activity": "one when activity_count is positive",
        },
        "cutoffs_days": sorted({int(value) for value in cutoffs_days}),
        "evaluations": evaluations,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kuleuven-path", type=Path, default=Path("data/raw/external/kuleuven/dataset.zip"))
    parser.add_argument("--synthetic-path", type=Path, default=Path("data/raw/synthetic"))
    parser.add_argument("--metrics-output", type=Path, default=Path("models/metrics/cross_dataset_transfer_metrics.json"))
    parser.add_argument("--cutoffs-days", type=int, nargs="+", default=[30, 60, 90])
    args = parser.parse_args()
    metrics = run_cross_dataset_transfer(args.kuleuven_path, args.synthetic_path, tuple(args.cutoffs_days))
    args.metrics_output.parent.mkdir(parents=True, exist_ok=True)
    args.metrics_output.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
