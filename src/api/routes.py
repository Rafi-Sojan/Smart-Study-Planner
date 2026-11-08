"""Minimal privacy-conscious risk-scoring routes."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request, Response

from src.api.schemas import (
    EvidenceSummary,
    LoginRequest,
    ModelCatalogResponse,
    ModelMetadataResponse,
    ModelOptionResponse,
    PlannedSessionResponse,
    RankedTaskResponse,
    RiskRequest,
    RiskResponse,
    SessionResponse,
    StudentStudyPlanRequest,
    StudentStudyPlanResponse,
    StudyPlanRequest,
    StudyPlanResponse,
)
from src.api.student_features import derive_student_feature_vector
from src.models.predict import FeatureContractError, predict_risk
from src.planner.prioritizer import PlanningTask, rank_tasks
from src.planner.recommendations import build_recommendations
from src.planner.scheduler import AvailabilityWindow, schedule_ranked_tasks


router = APIRouter()


def require_authentication(request: Request, *, csrf_protected: bool = False) -> None:
    """Accept a service API key or a valid browser session."""

    request.app.state.auth.authorize(request, csrf_protected=csrf_protected)


def _select_model(request: Request, model_id: str | None):
    catalog = request.app.state.model_catalog
    if not catalog:
        raise HTTPException(status_code=503, detail="Trusted model catalog is not loaded")
    try:
        return catalog.resolve(model_id)
    except KeyError as error:
        raise HTTPException(status_code=422, detail="Unknown or unavailable model_id") from error


def _calculate_plan(runtime, features, payload):
    """Run risk scoring and scheduling for either API request shape."""

    risk = predict_risk(runtime.model, features, runtime.threshold)
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
        [
            AvailabilityWindow(start=slot.start, end=slot.end)
            for slot in payload.availability
        ],
        session_minutes=payload.session_minutes,
        break_minutes=payload.break_minutes,
    )
    return risk, ranked, sessions, unscheduled


def _recommendations(risk, ranked, sessions, unscheduled) -> list[str]:
    return build_recommendations(
        float(risk["risk_score"]),
        ranked,
        sessions,
        unscheduled,
        risk_threshold=float(risk["threshold"]),
    )


def _ranked_responses(ranked) -> list[RankedTaskResponse]:
    return [
        RankedTaskResponse(
            task_id=item.task.task_id,
            title=item.task.title,
            subject=item.task.subject,
            priority_score=item.priority_score,
            remaining_minutes=item.task.remaining_minutes,
            rationale=list(item.rationale),
        )
        for item in ranked
    ]


def _session_responses(sessions) -> list[PlannedSessionResponse]:
    return [
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
    ]


def _session_response(request: Request) -> SessionResponse:
    settings = request.app.state.auth
    identity = settings.request_session(request)
    authenticated = bool(identity) or not settings.authentication_required
    return SessionResponse(
        authentication_required=settings.authentication_required,
        browser_login_enabled=settings.browser_login_enabled,
        authenticated=authenticated,
        username=identity.username if identity else None,
        expires_at=identity.expires_at if identity else None,
    )


@router.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/readyz")
def readyz(request: Request) -> dict[str, str]:
    if not request.app.state.model_catalog:
        raise HTTPException(status_code=503, detail="Trusted model catalog is not loaded")
    return {"status": "ready"}


@router.get("/v1/session", response_model=SessionResponse)
def session_status(request: Request, response: Response) -> SessionResponse:
    """Return browser-authentication state without exposing any secret."""

    response.headers["Cache-Control"] = "no-store"
    return _session_response(request)


@router.post("/v1/session", response_model=SessionResponse)
def create_session(
    payload: LoginRequest,
    request: Request,
    response: Response,
) -> SessionResponse:
    """Exchange a human credential for a signed HttpOnly session cookie."""

    settings = request.app.state.auth
    if not settings.browser_login_enabled:
        raise HTTPException(status_code=503, detail="Browser login is not configured")
    if request.headers.get("origin"):
        settings.require_same_origin(request)
    if not settings.verify_login(payload.username, payload.password):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    token = settings.issue_session(payload.username)
    identity = settings.read_session(token)
    response.set_cookie(
        key=settings.cookie_name,
        value=token,
        max_age=settings.session_ttl_seconds,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="strict",
        path="/",
    )
    response.headers["Cache-Control"] = "no-store"
    return SessionResponse(
        authentication_required=True,
        browser_login_enabled=True,
        authenticated=True,
        username=payload.username,
        expires_at=identity.expires_at if identity else None,
    )


@router.post("/v1/session/logout", response_model=SessionResponse)
def delete_session(request: Request, response: Response) -> SessionResponse:
    """Remove the browser session cookie."""

    settings = request.app.state.auth
    if settings.request_session(request):
        settings.require_same_origin(request)
    response.delete_cookie(
        settings.cookie_name,
        path="/",
        secure=settings.cookie_secure,
        httponly=True,
        samesite="strict",
    )
    response.headers["Cache-Control"] = "no-store"
    return SessionResponse(
        authentication_required=settings.authentication_required,
        browser_login_enabled=settings.browser_login_enabled,
        authenticated=not settings.authentication_required,
    )


@router.get("/v1/models", response_model=ModelCatalogResponse)
def model_catalog(request: Request) -> ModelCatalogResponse:
    """Return the bounded set of models that the current deployment allows."""

    require_authentication(request)
    catalog = request.app.state.model_catalog
    if not catalog or catalog.default_model_id is None:
        raise HTTPException(status_code=503, detail="Trusted model catalog is not loaded")
    return ModelCatalogResponse(
        default_model_id=catalog.default_model_id,
        models=[
            ModelOptionResponse(
                model_id=runtime.model_id,
                label=runtime.label,
                description=runtime.description,
                dataset=runtime.dataset,
                cutoff_days=runtime.cutoff_days,
                model_version=runtime.model_version,
                threshold=runtime.threshold,
                feature_count=runtime.feature_contract["feature_count"],
                is_default=runtime.model_id == catalog.default_model_id,
            )
            for runtime in catalog.models.values()
        ],
    )


@router.get("/v1/model-metadata", response_model=ModelMetadataResponse)
def model_metadata(request: Request, model_id: str | None = None) -> ModelMetadataResponse:
    require_authentication(request)
    runtime = _select_model(request, model_id)
    metadata = runtime.model_metadata
    contract = runtime.feature_contract
    return ModelMetadataResponse(
        model_id=runtime.model_id,
        label=runtime.label,
        description=runtime.description,
        dataset=runtime.dataset,
        cutoff_days=runtime.cutoff_days,
        model_version=runtime.model_version,
        model_source=runtime.model_source,
        registry_name=metadata.get("name"),
        registry_version=metadata.get("version"),
        threshold=runtime.threshold,
        threshold_source=runtime.threshold_source,
        feature_count=contract["feature_count"],
        feature_names=contract["feature_names"],
        feature_fields=contract["feature_fields"],
        feature_contract_sha256=contract["sha256"],
    )


@router.post("/v1/risk-score", response_model=RiskResponse)
def risk_score(payload: RiskRequest, request: Request) -> RiskResponse:
    require_authentication(request, csrf_protected=True)
    runtime = _select_model(request, payload.model_id)
    try:
        result = predict_risk(runtime.model, payload.features, runtime.threshold)
    except FeatureContractError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return RiskResponse(
        model_id=runtime.model_id,
        risk_score=float(result["risk_score"]),
        threshold=float(result["threshold"]),
        alert=bool(result["alert"]),
        model_version=runtime.model_version,
        feature_contract_sha256=runtime.feature_contract["sha256"],
        threshold_source=runtime.threshold_source,
    )


@router.post("/v1/study-plan", response_model=StudyPlanResponse)
def study_plan(payload: StudyPlanRequest, request: Request) -> StudyPlanResponse:
    """Score risk and produce a reviewable, capacity-constrained study plan."""

    require_authentication(request, csrf_protected=True)
    runtime = _select_model(request, payload.model_id)
    try:
        risk, ranked, sessions, unscheduled = _calculate_plan(
            runtime,
            payload.features,
            payload,
        )
    except (FeatureContractError, ValueError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return StudyPlanResponse(
        model_id=runtime.model_id,
        risk_score=float(risk["risk_score"]),
        threshold=float(risk["threshold"]),
        alert=bool(risk["alert"]),
        model_version=runtime.model_version,
        ranked_tasks=_ranked_responses(ranked),
        sessions=_session_responses(sessions),
        unscheduled_minutes=unscheduled,
        recommendations=_recommendations(risk, ranked, sessions, unscheduled),
        human_review_required=True,
    )


_GOAL_RECOMMENDATIONS = {
    "build_consistency": "Protect the scheduled sessions as a repeatable weekly routine.",
    "prepare_for_exams": "Use the earliest sessions for retrieval practice and spaced review.",
    "complete_assignments": "Start with the nearest incomplete deliverable and reserve review time.",
    "recover_missed_work": "Prioritise essential missed work before adding optional material.",
    "balance_subjects": "Review the subject distribution weekly and rebalance overloaded days.",
}


@router.post("/v1/student-study-plan", response_model=StudentStudyPlanResponse)
def student_study_plan(
    payload: StudentStudyPlanRequest,
    request: Request,
) -> StudentStudyPlanResponse:
    """Generate a plan while deriving the model contract on the server."""

    require_authentication(request, csrf_protected=True)
    runtime = _select_model(request, None)
    derivation = derive_student_feature_vector(
        runtime.feature_contract["feature_names"],
        payload.intake.model_dump(),
        [task.model_dump() for task in payload.tasks],
        [slot.model_dump() for slot in payload.availability],
        cutoff_days=runtime.cutoff_days,
    )
    try:
        risk, ranked, sessions, unscheduled = _calculate_plan(
            runtime,
            derivation.values,
            payload,
        )
    except (FeatureContractError, ValueError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    recommendations = _recommendations(risk, ranked, sessions, unscheduled)
    recommendations.insert(
        0,
        _GOAL_RECOMMENDATIONS[payload.intake.primary_goal],
    )
    return StudentStudyPlanResponse(
        support_level=(
            "review_recommended" if bool(risk["alert"]) else "standard_planning"
        ),
        alert=bool(risk["alert"]),
        ranked_tasks=_ranked_responses(ranked),
        sessions=_session_responses(sessions),
        unscheduled_minutes=unscheduled,
        recommendations=recommendations,
        evidence=EvidenceSummary(
            mapped_feature_count=derivation.mapped_feature_count,
            unavailable_feature_count=derivation.unavailable_feature_count,
            coverage_percent=derivation.coverage_percent,
            reliability=derivation.reliability,
            source_labels=list(derivation.source_labels),
            message=derivation.message,
        ),
        human_review_required=True,
    )
