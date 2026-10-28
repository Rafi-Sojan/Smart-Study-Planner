"""Run a real-model smoke request against the FastAPI application."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path


def run_api_smoke(
    data_dir: str | Path,
    metrics_path: str | Path,
    model_dir: str | Path,
    cutoff: int = 30,
) -> None:
    from fastapi.testclient import TestClient

    from src.features.synthetic_features import build_cutoff_features
    from src.models.synthetic_baseline import DROP_COLUMNS

    metrics = json.loads(Path(metrics_path).read_text(encoding="utf-8"))
    evaluation = metrics["evaluations"][str(cutoff)]
    best_model = evaluation["best_model"]
    model_path = Path(model_dir) / f"day_{cutoff}_{best_model}.pkl"
    os.environ["MODEL_PATH"] = str(model_path)
    os.environ["ALLOW_TRUSTED_PICKLE_MODEL"] = "1"
    os.environ["MODEL_VERSION"] = f"smoke-day-{cutoff}"

    from src.api.main import create_app

    features = build_cutoff_features(data_dir, (cutoff,))[cutoff]
    feature_columns = [column for column in features.columns if column not in DROP_COLUMNS]
    payload = {"features": json.loads(features[feature_columns].iloc[[0]].to_json(orient="records"))[0]}
    client = TestClient(create_app())
    assert client.get("/readyz").status_code == 200
    response = client.post("/v1/risk-score", json=payload)
    if response.status_code != 200:
        raise RuntimeError(f"Inference smoke request failed: {response.status_code} {response.text}")
    body = response.json()
    if not 0 <= body["risk_score"] <= 1:
        raise RuntimeError(f"Risk score is outside [0, 1]: {body['risk_score']}")
    print(f"API smoke passed with model {best_model} at cutoff {cutoff}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Smoke-test FastAPI with a trained synthetic model")
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--metrics", type=Path, required=True)
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--cutoff", type=int, default=30)
    args = parser.parse_args()
    run_api_smoke(args.data_dir, args.metrics, args.model_dir, args.cutoff)


if __name__ == "__main__":
    main()
