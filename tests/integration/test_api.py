from fastapi.testclient import TestClient
import numpy as np
import pytest

from src.api.main import create_app
from src.api.auth import hash_password
from src.api.model_catalog import ModelCatalog, ModelRuntime
from src.models.predict import feature_contract


class _Model:
    feature_names_in_ = np.array(["activity_count"])

    def predict_proba(self, frame):
        score = min(float(frame.iloc[0]["activity_count"]) / 100.0, 1.0)
        return np.array([[1.0 - score, score]])


class _ConservativeModel:
    feature_names_in_ = np.array(["activity_count"])

    def predict_proba(self, frame):
        score = min(float(frame.iloc[0]["activity_count"]) / 200.0, 1.0)
        return np.array([[1.0 - score, score]])


class _AttendanceModel:
    feature_names_in_ = np.array(["attendance_pct_mean"])

    def predict_proba(self, frame):
        attendance = float(frame.iloc[0]["attendance_pct_mean"])
        score = max(0.0, min((100.0 - attendance) / 100.0, 1.0))
        return np.array([[1.0 - score, score]])


def _runtime(
    model_id: str,
    model,
    *,
    label: str | None = None,
    cutoff_days: int | None = None,
) -> ModelRuntime:
    return ModelRuntime(
        model_id=model_id,
        label=label or model_id,
        description=f"Test model {model_id}",
        dataset="test",
        cutoff_days=cutoff_days,
        model=model,
        threshold=0.5,
        threshold_source="test",
        model_version=f"{model_id}/1",
        model_source="test-model",
        model_metadata={},
        feature_contract=feature_contract(model),
    )


def _install_catalog(app, *runtimes: ModelRuntime, default_model_id: str) -> None:
    catalog = ModelCatalog(
        models={runtime.model_id: runtime for runtime in runtimes},
        default_model_id=default_model_id,
    )
    app.state.model_catalog = catalog
    default = catalog.default()
    app.state.model = default.model
    app.state.model_source = default.model_source
    app.state.model_version = default.model_version
    app.state.feature_contract = default.feature_contract


def _loaded_client(monkeypatch) -> TestClient:
    for name in (
        "API_KEY",
        "MODEL_PATH",
        "MODEL_URI",
        "MODEL_CATALOG_JSON",
        "DEFAULT_MODEL_ID",
        "APP_ENV",
        "WEB_AUTH_USERNAME",
        "WEB_AUTH_PASSWORD_HASH",
        "SESSION_SECRET",
        "CORS_ALLOWED_ORIGINS",
    ):
        monkeypatch.delenv(name, raising=False)
    app = create_app()
    _install_catalog(app, _runtime("default", _Model()), default_model_id="default")
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
    monkeypatch.delenv("MODEL_CATALOG_JSON", raising=False)
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


def test_student_plan_derives_features_and_hides_model_internals(monkeypatch) -> None:
    client = _loaded_client(monkeypatch)
    _install_catalog(
        client.app,
        _runtime("default", _AttendanceModel(), cutoff_days=30),
        default_model_id="default",
    )
    payload = {
        "intake": {
            "primary_goal": "complete_assignments",
            "subjects": ["Mathematics"],
            "course_type": "theory",
            "current_term": 3,
            "attendance_percent": 80,
            "recent_score_percent": 70,
            "submission_rate_percent": 75,
        },
        "planning_time": "2026-01-10T12:00:00+00:00",
        "tasks": [
            {
                "task_id": "assignment-1",
                "title": "Complete assignment",
                "subject": "Mathematics",
                "deadline": "2026-01-12T12:00:00+00:00",
                "estimated_minutes": 60,
                "difficulty": 3,
                "importance": 5,
            }
        ],
        "availability": [
            {
                "start": "2026-01-10T14:00:00+00:00",
                "end": "2026-01-10T15:00:00+00:00",
            }
        ],
        "session_minutes": 50,
        "break_minutes": 10,
    }

    response = client.post("/v1/student-study-plan", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["support_level"] == "standard_planning"
    assert body["evidence"]["institutional_data_connected"] is False
    assert body["evidence"]["mapped_feature_count"] == 1
    assert "model_id" not in body
    assert "model_version" not in body
    assert "feature_contract_sha256" not in body
    assert body["sessions"][0]["task_id"] == "assignment-1"


def test_user_can_list_and_select_an_allowlisted_model(monkeypatch) -> None:
    client = _loaded_client(monkeypatch)
    app = client.app
    _install_catalog(
        app,
        _runtime("early-30", _Model(), label="30-day early warning", cutoff_days=30),
        _runtime(
            "balanced-60",
            _ConservativeModel(),
            label="60-day balanced model",
            cutoff_days=60,
        ),
        default_model_id="early-30",
    )

    catalog = client.get("/v1/models")
    selected = client.post(
        "/v1/risk-score",
        json={"model_id": "balanced-60", "features": {"activity_count": 80}},
    )
    unknown = client.post(
        "/v1/risk-score",
        json={"model_id": "not-configured", "features": {"activity_count": 80}},
    )

    assert catalog.status_code == 200
    assert catalog.json()["default_model_id"] == "early-30"
    assert [item["model_id"] for item in catalog.json()["models"]] == [
        "early-30",
        "balanced-60",
    ]
    assert selected.status_code == 200
    assert selected.json()["model_id"] == "balanced-60"
    assert selected.json()["risk_score"] == 0.4
    assert unknown.status_code == 422


def test_browser_session_authenticates_without_exposing_api_key(monkeypatch) -> None:
    monkeypatch.setenv("API_KEY", "machine-only-key")
    monkeypatch.setenv("WEB_AUTH_USERNAME", "planner-admin")
    monkeypatch.setenv(
        "WEB_AUTH_PASSWORD_HASH",
        hash_password("a-strong-test-password", iterations=100_000),
    )
    monkeypatch.setenv("SESSION_SECRET", "s" * 48)
    monkeypatch.delenv("MODEL_PATH", raising=False)
    monkeypatch.delenv("MODEL_URI", raising=False)
    monkeypatch.delenv("MODEL_CATALOG_JSON", raising=False)
    monkeypatch.delenv("APP_ENV", raising=False)
    app = create_app()
    _install_catalog(app, _runtime("default", _Model()), default_model_id="default")
    client = TestClient(app)

    unauthenticated = client.get("/v1/model-metadata")
    login = client.post(
        "/v1/session",
        headers={"Origin": "http://testserver"},
        json={"username": "planner-admin", "password": "a-strong-test-password"},
    )
    authenticated = client.get("/v1/model-metadata")

    assert unauthenticated.status_code == 401
    assert login.status_code == 200
    assert login.json()["authenticated"] is True
    assert "httponly" in login.headers["set-cookie"].lower()
    assert "machine-only-key" not in login.text
    assert authenticated.status_code == 200


def test_browser_session_rejects_cross_origin_mutation(monkeypatch) -> None:
    monkeypatch.setenv("WEB_AUTH_USERNAME", "planner-admin")
    monkeypatch.setenv(
        "WEB_AUTH_PASSWORD_HASH",
        hash_password("a-strong-test-password", iterations=100_000),
    )
    monkeypatch.setenv("SESSION_SECRET", "s" * 48)
    monkeypatch.delenv("API_KEY", raising=False)
    monkeypatch.delenv("MODEL_PATH", raising=False)
    monkeypatch.delenv("MODEL_URI", raising=False)
    monkeypatch.delenv("MODEL_CATALOG_JSON", raising=False)
    monkeypatch.delenv("APP_ENV", raising=False)
    app = create_app()
    _install_catalog(app, _runtime("default", _Model()), default_model_id="default")
    client = TestClient(app)
    client.post(
        "/v1/session",
        headers={"Origin": "http://testserver"},
        json={"username": "planner-admin", "password": "a-strong-test-password"},
    )

    response = client.post(
        "/v1/risk-score",
        headers={"Origin": "https://attacker.invalid"},
        json={"features": {"activity_count": 75}},
    )

    assert response.status_code == 403


def test_configured_cors_origin_supports_credentialed_preflight(monkeypatch) -> None:
    for name in (
        "API_KEY",
        "MODEL_PATH",
        "MODEL_URI",
        "MODEL_CATALOG_JSON",
        "APP_ENV",
        "WEB_AUTH_USERNAME",
        "WEB_AUTH_PASSWORD_HASH",
        "SESSION_SECRET",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "http://localhost:5173")
    app = create_app()
    _install_catalog(app, _runtime("default", _Model()), default_model_id="default")
    client = TestClient(app)

    response = client.options(
        "/v1/risk-score",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert response.headers["access-control-allow-credentials"] == "true"
