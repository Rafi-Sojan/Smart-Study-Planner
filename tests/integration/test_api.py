from fastapi.testclient import TestClient
import numpy as np
import pytest

from src.api.main import create_app
from src.models.predict import feature_contract


class _Model:
    feature_names_in_ = np.array(["activity_count"])

    def predict_proba(self, frame):
        score = min(float(frame.iloc[0]["activity_count"]) / 100.0, 1.0)
        return np.array([[1.0 - score, score]])


def _loaded_client(monkeypatch) -> TestClient:
    monkeypatch.delenv("API_KEY", raising=False)
    monkeypatch.delenv("MODEL_PATH", raising=False)
    monkeypatch.delenv("MODEL_URI", raising=False)
    monkeypatch.delenv("APP_ENV", raising=False)
    app = create_app()
    app.state.model = _Model()
    app.state.model_source = "test-model"
    app.state.model_version = "test/1"
    app.state.feature_contract = feature_contract(app.state.model)
    return TestClient(app)


def test_health_endpoint_is_available_without_a_model() -> None:
    client = TestClient(create_app())
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readiness_refuses_to_claim_model_availability() -> None:
    client = TestClient(create_app())
    response = client.get("/readyz")
    assert response.status_code == 503


def test_metrics_endpoint_is_available() -> None:
    client = TestClient(create_app())
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "smart_study_planner_http_requests_total" in response.text


def test_api_key_is_required_when_configured(monkeypatch) -> None:
    monkeypatch.setenv("API_KEY", "test-key")
    client = TestClient(create_app())
    response = client.post("/v1/risk-score", json={"features": {"x": 1}})
    assert response.status_code == 401


def test_production_refuses_to_start_without_registered_model(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("MODEL_PATH", raising=False)
    monkeypatch.delenv("MODEL_URI", raising=False)
    with pytest.raises(RuntimeError, match="immutable registered MODEL_URI"):
        create_app()


def test_risk_endpoint_enforces_the_fitted_feature_contract(monkeypatch) -> None:
    client = _loaded_client(monkeypatch)
    rejected = client.post("/v1/risk-score", json={"features": {"wrong": 1}})
    accepted = client.post("/v1/risk-score", json={"features": {"activity_count": 75}})

    assert rejected.status_code == 422
    assert accepted.status_code == 200
    assert accepted.json()["risk_score"] == 0.75
    assert len(accepted.json()["feature_contract_sha256"]) == 64


def test_study_plan_endpoint_returns_reviewable_non_overlapping_sessions(monkeypatch) -> None:
    client = _loaded_client(monkeypatch)
    payload = {
        "features": {"activity_count": 80},
        "planning_time": "2026-01-10T12:00:00+00:00",
        "tasks": [
            {
                "task_id": "assignment-1",
                "title": "Complete assignment",
                "subject": "Mathematics",
                "deadline": "2026-01-12T12:00:00+00:00",
                "estimated_minutes": 120,
                "difficulty": 4,
                "importance": 5,
            }
        ],
        "availability": [
            {"start": "2026-01-10T14:00:00+00:00", "end": "2026-01-10T16:00:00+00:00"}
        ],
        "session_minutes": 50,
        "break_minutes": 10,
    }

    response = client.post("/v1/study-plan", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["human_review_required"] is True
    assert [session["study_minutes"] for session in body["sessions"]] == [50, 50]
    assert body["unscheduled_minutes"] == {"assignment-1": 20}
