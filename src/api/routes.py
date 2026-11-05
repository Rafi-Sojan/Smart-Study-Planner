"""Minimal privacy-conscious risk-scoring routes."""

from __future__ import annotations

import os
import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request

from src.api.schemas import (
    ModelMetadataResponse,
    PlannedSessionResponse,
    RankedTaskResponse,
    RiskRequest,
    RiskResponse,
    StudyPlanRequest,
    StudyPlanResponse,
)
from src.models.predict import FeatureContractError, predict_risk
from src.planner.prioritizer import PlanningTask, rank_tasks
from src.planner.recommendations import build_recommendations
from src.planner.scheduler import AvailabilityWindow, schedule_ranked_tasks


router = APIRouter()


def require_api_key(request: Request) -> None:
    """Enforce the configured service credential without logging its value."""

    expected_api_key = os.getenv("API_KEY")
    supplied_api_key = request.headers.get("x-api-key", "")
    if expected_api_key and not secrets.compare_digest(supplied_api_key, expected_api_key):
        raise HTTPException(status_code=401, detail="Invalid API key")


@router.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/readyz")
def readyz(request: Request) -> dict[str, str]:
    if getattr(request.app.state, "model", None) is None:
        raise HTTPException(status_code=503, detail="Trusted model is not loaded")
    return {"status": "ready"}


@router.get("/v1/model-metadata", response_model=ModelMetadataResponse)
def model_metadata(request: Request) -> ModelMetadataResponse:
    require_api_key(request)
    if getattr(request.app.state, "model", None) is None:
        raise HTTPException(status_code=503, detail="Trusted model is not loaded")
    metadata = request.app.state.model_metadata
    contract = request.app.state.feature_contract
    return ModelMetadataResponse(
        model_version=request.app.state.model_version,
        model_source=request.app.state.model_source,
        registry_name=metadata.get("name"),
        registry_version=metadata.get("version"),
        threshold=request.app.state.threshold,
        threshold_source=request.app.state.threshold_source,
        feature_count=contract["feature_count"],
        feature_names=contract["feature_names"],
        feature_contract_sha256=contract["sha256"],
    )


@router.post("/v1/risk-score", response_model=RiskResponse)
def risk_score(payload: RiskRequest, request: Request) -> RiskResponse:
    require_api_key(request)
    model = getattr(request.app.state, "model", None)
    if model is None:
        raise HTTPException(status_code=503, detail="Trusted model is not loaded")
    try:
        result = predict_risk(model, payload.features, request.app.state.threshold)
    except FeatureContractError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return RiskResponse(
        risk_score=float(result["risk_score"]),
        threshold=float(result["threshold"]),
        alert=bool(result["alert"]),
        model_version=request.app.state.model_version,
        feature_contract_sha256=request.app.state.feature_contract["sha256"],
        threshold_source=request.app.state.threshold_source,
    )


@router.post("/v1/study-plan", response_model=StudyPlanResponse)
def study_plan(payload: StudyPlanRequest, request: Request) -> StudyPlanResponse:
    """Score risk and produce a reviewable, capacity-constrained study plan."""

    require_api_key(request)
    model = getattr(request.app.state, "model", None)
    if model is None:
        raise HTTPException(status_code=503, detail="Trusted model is not loaded")
    try:
        risk = predict_risk(model, payload.features, request.app.state.threshold)
        planning_time = payload.planning_time or datetime.now(timezone.utc)
        tasks = [
            PlanningTask(
                task_id=task.task_id,
                title=task.title,
                subject=task.subject,
                deadline=task.deadline,
                estimated_minutes=task.estimated_minutes,
                completed_minutes=task.completed_minutes,
                difficulty=task.difficulty,
                importance=task.importance,
            )
            for task in payload.tasks
        ]
        ranked = rank_tasks(
            tasks,
            float(risk["risk_score"]),
            planning_time,
            risk_threshold=float(risk["threshold"]),
        )
        sessions, unscheduled = schedule_ranked_tasks(
            ranked,
            [AvailabilityWindow(start=slot.start, end=slot.end) for slot in payload.availability],
            session_minutes=payload.session_minutes,
            break_minutes=payload.break_minutes,
        )
    except (FeatureContractError, ValueError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return StudyPlanResponse(
        risk_score=float(risk["risk_score"]),
        threshold=float(risk["threshold"]),
        alert=bool(risk["alert"]),
        model_version=request.app.state.model_version,
        ranked_tasks=[
            RankedTaskResponse(
                task_id=item.task.task_id,
                priority_score=item.priority_score,
                remaining_minutes=item.task.remaining_minutes,
                rationale=list(item.rationale),
            )
            for item in ranked
        ],
        sessions=[
            PlannedSessionResponse(
                task_id=session.task_id,
                title=session.title,
                subject=session.subject,
                start=session.start,
                end=session.end,
                study_minutes=session.study_minutes,
                priority_score=session.priority_score,
            )
            for session in sessions
        ],
        unscheduled_minutes=unscheduled,
        recommendations=build_recommendations(
            float(risk["risk_score"]),
            ranked,
            sessions,
            unscheduled,
            risk_threshold=float(risk["threshold"]),
        ),
        human_review_required=True,
    )
