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
