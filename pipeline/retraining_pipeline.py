"""Explicit retraining command with an approval gate.

Automatic retraining is intentionally not enabled: a new model must be
reviewed, evaluated, and registered as a new candidate before promotion.
"""

from __future__ import annotations

import argparse

from pipeline.early_warning_pipeline import run_early_warning
from pipeline.synthetic_baseline_pipeline import run_synthetic_baseline_pipeline
from pipeline.training_pipeline import run_training


def main() -> None:
    parser = argparse.ArgumentParser(description="Run an explicitly approved retraining job")
    parser.add_argument("--task", choices=("oulad", "early-warning", "synthetic"), required=True)
    parser.add_argument("--data-dir", required=True)
    parser.add_argument("--approve", action="store_true", help="Confirm human review of the retraining request")
    args = parser.parse_args()
    if not args.approve:
        raise SystemExit("Retraining is blocked until a human passes --approve")
    if args.task == "oulad":
        run_training(args.data_dir)
    elif args.task == "early-warning":
        run_early_warning(args.data_dir)
    else:
        run_synthetic_baseline_pipeline(args.data_dir)


if __name__ == "__main__":
    main()
