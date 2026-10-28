"""FastAPI application with explicit trusted-model loading."""

from __future__ import annotations

import os
from time import perf_counter
from pathlib import Path

from fastapi import FastAPI
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from starlette.responses import Response

from src.api.metrics import REQUEST_COUNT, REQUEST_LATENCY
from src.api.routes import router
from src.models.predict import load_registered_model, load_trusted_model


def create_app() -> FastAPI:
    app = FastAPI(
        title="Smart Study Planner Risk API",
        version=os.getenv("MODEL_VERSION", "development"),
        docs_url="/docs" if os.getenv("ENABLE_API_DOCS", "0") == "1" else None,
        redoc_url=None,
    )
    app.state.model = None
    app.state.threshold = float(os.getenv("MODEL_THRESHOLD", "0.5"))
    app.state.model_version = os.getenv("MODEL_VERSION", "development")
    model_path = os.getenv("MODEL_PATH")
    model_uri = os.getenv("MODEL_URI")
    if not model_path and not model_uri and Path("/models/model.pkl").is_file():
        model_path = "/models/model.pkl"
    if model_path and model_uri:
        raise RuntimeError("Configure only one of MODEL_PATH or MODEL_URI")
    if model_uri:
        app.state.model = load_registered_model(model_uri)
        app.state.model_source = model_uri
    elif model_path:
        app.state.model = load_trusted_model(
            Path(model_path),
            expected_sha256=os.getenv("MODEL_SHA256"),
        )
        app.state.model_source = str(model_path)

    @app.middleware("http")
    async def observe_requests(request, call_next):
        started = perf_counter()
        status = "500"
        try:
            response = await call_next(request)
            status = str(response.status_code)
            return response
        finally:
            path = request.url.path
            REQUEST_COUNT.labels(request.method, path, status).inc()
            REQUEST_LATENCY.labels(request.method, path).observe(perf_counter() - started)

    @app.get("/metrics", include_in_schema=False)
    def metrics() -> Response:
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    app.include_router(router)
    return app


app = create_app()
