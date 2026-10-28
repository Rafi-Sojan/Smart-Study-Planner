"""Minimal privacy-conscious risk-scoring routes."""

from __future__ import annotations

import os

from fastapi import APIRouter, HTTPException, Request

from src.api.schemas import RiskRequest, RiskResponse
from src.models.predict import predict_risk


router = APIRouter()


@router.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/readyz")
def readyz(request: Request) -> dict[str, str]:
    if getattr(request.app.state, "model", None) is None:
        raise HTTPException(status_code=503, detail="Trusted model is not loaded")
    return {"status": "ready"}


@router.post("/v1/risk-score", response_model=RiskResponse)
def risk_score(payload: RiskRequest, request: Request) -> RiskResponse:
    expected_api_key = os.getenv("API_KEY")
    if expected_api_key and request.headers.get("x-api-key") != expected_api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")
    model = getattr(request.app.state, "model", None)
    if model is None:
        raise HTTPException(status_code=503, detail="Trusted model is not loaded")
    result = predict_risk(model, payload.features, request.app.state.threshold)
    return RiskResponse(
        risk_score=float(result["risk_score"]),
        threshold=float(result["threshold"]),
        alert=bool(result["alert"]),
        model_version=request.app.state.model_version,
    )
