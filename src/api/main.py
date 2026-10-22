"""FastAPI application with explicit trusted-model loading."""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI

from src.api.routes import router
from src.models.predict import load_trusted_model


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
    if model_path:
        app.state.model = load_trusted_model(
            Path(model_path),
            expected_sha256=os.getenv("MODEL_SHA256"),
        )
    app.include_router(router)
    return app


app = create_app()
