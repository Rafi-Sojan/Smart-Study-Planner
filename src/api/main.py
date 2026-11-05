"""FastAPI application with explicit trusted-model loading."""

from __future__ import annotations

import os
from time import perf_counter
from pathlib import Path

from fastapi import FastAPI
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.responses import Response

from src.api.metrics import REQUEST_COUNT, REQUEST_LATENCY
from src.api.routes import router
from src.models.predict import feature_contract, load_registered_model, load_trusted_model, validate_threshold
from src.tracking.model_registry import verify_registered_model


def create_app() -> FastAPI:
    environment = os.getenv("APP_ENV", "development").strip().lower()
    production = environment == "production"
    app = FastAPI(
        title="Smart Study Planner Risk API",
        version=os.getenv("MODEL_VERSION", "development"),
        docs_url="/docs" if os.getenv("ENABLE_API_DOCS", "0") == "1" else None,
        redoc_url=None,
    )
    app.state.model = None
    app.state.threshold = validate_threshold(float(os.getenv("MODEL_THRESHOLD", "0.5")))
    app.state.threshold_source = "development_default"
    app.state.model_version = os.getenv("MODEL_VERSION", "development")
    app.state.model_source = "not_configured"
    app.state.model_metadata = {}
    app.state.feature_contract = {
        "feature_names": [],
        "feature_count": 0,
        "sha256": "0" * 64,
        "source": "unavailable",
    }
    model_path = os.getenv("MODEL_PATH")
    model_uri = os.getenv("MODEL_URI")
    if not model_path and not model_uri and Path("/models/model.pkl").is_file():
        model_path = "/models/model.pkl"
    if model_path and model_uri:
        raise RuntimeError("Configure only one of MODEL_PATH or MODEL_URI")
    if production and not model_uri:
        raise RuntimeError("Production requires an immutable registered MODEL_URI")
    if production and not os.getenv("API_KEY"):
        raise RuntimeError("Production requires API_KEY")
    if model_uri:
        configured_threshold = os.getenv("MODEL_THRESHOLD")
        verification = verify_registered_model(
            model_uri,
            expected_threshold=float(configured_threshold) if configured_threshold else None,
            require_deployment_eligible=production,
            require_fairness=production,
            require_immutable_uri=production,
        )
        if not verification["passed"]:
            failed = [check["name"] for check in verification["checks"] if not check["passed"]]
            raise RuntimeError(f"Registered model verification failed: {failed}")
        registry_threshold = verification["operating_threshold"]
        if registry_threshold is None:
            raise RuntimeError("Registered model has no approved operating_threshold tag")
        app.state.threshold = validate_threshold(registry_threshold)
        app.state.threshold_source = "mlflow_registry_tag"
        app.state.model = load_registered_model(verification["resolved_uri"])
        app.state.model_source = verification["resolved_uri"]
        app.state.model_metadata = verification
        app.state.model_version = os.getenv(
            "MODEL_VERSION", f"{verification['name']}/{verification['version']}"
        )
    elif model_path:
        if production:
            raise RuntimeError("Production refuses local pickle models; use MODEL_URI")
        app.state.model = load_trusted_model(
            Path(model_path),
            expected_sha256=os.getenv("MODEL_SHA256"),
        )
        app.state.model_source = str(model_path)
        app.state.threshold_source = (
            "deployment_environment" if os.getenv("MODEL_THRESHOLD") else "development_default"
        )

    if app.state.model is not None:
        app.state.feature_contract = feature_contract(app.state.model)
        if not app.state.feature_contract["feature_names"]:
            raise RuntimeError("Loaded model does not expose a raw feature contract")
        registry_contract = app.state.model_metadata.get("feature_contract_sha256")
        if registry_contract and registry_contract != app.state.feature_contract["sha256"]:
            raise RuntimeError("Loaded model feature contract does not match registry metadata")

    allowed_hosts = [
        value.strip()
        for value in os.getenv("ALLOWED_HOSTS", "").split(",")
        if value.strip()
    ]
    if production and not allowed_hosts:
        raise RuntimeError("Production requires ALLOWED_HOSTS")
    if allowed_hosts:
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts)

    @app.middleware("http")
    async def observe_requests(request, call_next):
        started = perf_counter()
        status = "500"
        try:
            response = await call_next(request)
            status = str(response.status_code)
            return response
        finally:
            route = request.scope.get("route")
            path_template = getattr(route, "path", "__unmatched__")
            REQUEST_COUNT.labels(request.method, path_template, status).inc()
            REQUEST_LATENCY.labels(request.method, path_template).observe(
                perf_counter() - started
            )

    @app.get("/metrics", include_in_schema=False)
    def metrics() -> Response:
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    app.include_router(router)
    return app


app = create_app()
