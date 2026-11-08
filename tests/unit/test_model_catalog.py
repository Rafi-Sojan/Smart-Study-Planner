import json

import pytest

from pipeline.verify_model_catalog import run_catalog_verification
from src.api.model_catalog import load_model_catalog, parse_model_catalog


def _catalog_payload() -> dict:
    return {
        "default_model_id": "oulad-day-30",
        "models": [
            {
                "id": "oulad-day-30",
                "label": "OULAD 30-day early warning",
                "description": "Earlier intervention model",
                "dataset": "OULAD",
                "cutoff_days": 30,
                "model_uri": "models:/oulad-day-30/7",
                "threshold": 0.35,
            },
            {
                "id": "oulad-day-60",
                "label": "OULAD 60-day early warning",
                "description": "Mid-course evidence model",
                "dataset": "OULAD",
                "cutoff_days": 60,
                "model_uri": "models:/oulad-day-60/4",
                "threshold": 0.41,
            },
        ],
    }


def test_catalog_parser_preserves_user_facing_model_options() -> None:
    specs, default_id = parse_model_catalog(json.dumps(_catalog_payload()))

    assert default_id == "oulad-day-30"
    assert [spec.model_id for spec in specs] == ["oulad-day-30", "oulad-day-60"]
    assert specs[1].cutoff_days == 60
    assert specs[1].threshold == 0.41


def test_catalog_parser_rejects_duplicate_or_unlisted_defaults() -> None:
    payload = _catalog_payload()
    payload["models"][1]["id"] = "oulad-day-30"
    with pytest.raises(ValueError, match="unique"):
        parse_model_catalog(json.dumps(payload))

    payload = _catalog_payload()
    payload["default_model_id"] = "not-listed"
    with pytest.raises(ValueError, match="DEFAULT_MODEL_ID"):
        parse_model_catalog(json.dumps(payload))


def test_production_catalog_refuses_local_pickle_paths(monkeypatch) -> None:
    payload = {
        "models": [
            {
                "id": "local-model",
                "model_path": "models/local.pkl",
                "threshold": 0.5,
            }
        ]
    }
    monkeypatch.setenv("MODEL_CATALOG_JSON", json.dumps(payload))
    monkeypatch.delenv("MODEL_URI", raising=False)
    monkeypatch.delenv("MODEL_PATH", raising=False)

    with pytest.raises(RuntimeError, match="refuses local model_path"):
        load_model_catalog(production=True)


def test_catalog_release_verification_checks_every_registered_model() -> None:
    calls: list[tuple[str, float | None]] = []

    def verifier(model_uri: str, *, expected_threshold: float | None, **_kwargs):
        calls.append((model_uri, expected_threshold))
        return {"passed": True, "name": model_uri, "version": "1"}

    report = run_catalog_verification(
        json.dumps(_catalog_payload()),
        verifier=verifier,
    )

    assert report["passed"] is True
    assert report["default_model_id"] == "oulad-day-30"
    assert calls == [
        ("models:/oulad-day-30/7", 0.35),
        ("models:/oulad-day-60/4", 0.41),
    ]
