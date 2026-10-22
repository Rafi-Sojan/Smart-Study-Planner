"""Explicit, checksum-verified batch inference entry point."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from src.models.predict import load_trusted_model


def run_inference(
    model_path: str | Path,
    input_path: str | Path,
    output_path: str | Path,
    threshold: float = 0.5,
) -> None:
    """Score a CSV using a trusted model without writing input identifiers."""

    model = load_trusted_model(model_path)
    frame = pd.read_csv(input_path)
    probabilities = model.predict_proba(frame)[:, 1]
    result = pd.DataFrame(
        {
            "row_number": range(len(frame)),
            "risk_score": probabilities,
            "alert": probabilities >= threshold,
            "threshold": threshold,
        }
    )
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(path, index=False)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run trusted batch inference")
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--threshold", type=float, default=0.5)
    args = parser.parse_args()
    if not 0 <= args.threshold <= 1:
        raise SystemExit("--threshold must be between 0 and 1")
    run_inference(args.model, args.input, args.output, args.threshold)


if __name__ == "__main__":
    main()
