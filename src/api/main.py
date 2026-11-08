"""FastAPI application with explicit trusted-model loading."""

from __future__ import annotations

import os
from time import perf_counter

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.responses import Response

from src.api.auth import AuthSettings
from src.api.metrics import REQUEST_COUNT, REQUEST_LATENCY
from src.api.model_catalog import load_model_catalog
from src.api.routes import router


def create_app() -> FastAPI:
    environment = os.getenv("APP_ENV", "development").strip().lower()
    production = environment == "production"
    app = FastAPI(
        title="Smart Study Planner Risk API",
        version=os.getenv("MODEL_VERSION", "development"),
        docs_url="/docs" if os.getenv("ENABLE_API_DOCS", "0") == "1" else None,
        redoc_url=None,
    )
    app.state.model_catalog = load_model_catalog(production=production)
    default_model = app.state.model_catalog.default()
    app.state.model = None
    app.state.threshold = 0.5
    app.state.threshold_source = "development_default"
    app.state.model_version = os.getenv("MODEL_VERSION", "development")
    app.state.model_source = "not_configured"
    app.state.model_metadata = {}
    app.state.feature_contract = {
        "feature_names": [],
        "feature_fields": [],
        "feature_count": 0,
        "sha256": "0" * 64,
        "source": "unavailable",
    }
    if default_model is not None:
        # Mirror the default runtime on the legacy state attributes for existing
        # health checks and operators that inspect app.state directly.
        app.state.model = default_model.model
        app.state.threshold = default_model.threshold
        app.state.threshold_source = default_model.threshold_source
        app.state.model_version = default_model.model_version
        app.state.model_source = default_model.model_source
        app.state.model_metadata = default_model.model_metadata
        app.state.feature_contract = default_model.feature_contract
        app.version = default_model.model_version

    app.state.auth = AuthSettings.from_environment(production=production)
    app.state.cors_origins = app.state.auth.cors_origins
    if app.state.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(app.state.cors_origins),
            allow_credentials=True,
            allow_methods=["GET", "POST", "OPTIONS"],
            allow_headers=["Content-Type", "X-API-Key"],
        )

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
            response.headers.setdefault("X-Content-Type-Options", "nosniff")
            response.headers.setdefault("X-Frame-Options", "DENY")
            response.headers.setdefault("Referrer-Policy", "no-referrer")
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
