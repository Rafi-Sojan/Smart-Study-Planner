from fastapi.testclient import TestClient

from src.api.main import create_app


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
