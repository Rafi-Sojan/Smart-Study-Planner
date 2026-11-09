"""Validated API request and response schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictFloat,
    StrictInt,
    StrictStr,
    field_validator,
    model_validator,
)


FeatureValue = StrictBool | StrictInt | StrictFloat | StrictStr | None
MODEL_ID_PATTERN = r"^[a-z][a-z0-9-]{0,62}$"


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=1, max_length=512)


class SessionResponse(BaseModel):
    authentication_required: bool
    browser_login_enabled: bool
    authenticated: bool
    username: str | None = None
    expires_at: datetime | None = None


class RiskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model_id: str | None = Field(default=None, pattern=MODEL_ID_PATTERN)
    features: dict[str, FeatureValue] = Field(..., min_length=1, max_length=200)


class RiskResponse(BaseModel):
    model_id: str
    risk_score: float = Field(ge=0, le=1)
    threshold: float = Field(ge=0, le=1)
    alert: bool
    model_version: str
    feature_contract_sha256: str
    threshold_source: str


class FeatureField(BaseModel):
    name: str
    kind: str = Field(pattern=r"^(number|string|boolean|unknown)$")
    required: bool = True


class ModelMetadataResponse(BaseModel):
    model_id: str
    label: str
    description: str
    dataset: str | None = None
    cutoff_days: int | None = Field(default=None, gt=0)
    model_version: str
    model_source: str
    registry_name: str | None = None
    registry_version: str | None = None
    threshold: float = Field(gt=0, lt=1)
    threshold_source: str
    feature_count: int = Field(ge=0)
    feature_names: list[str]
    feature_fields: list[FeatureField]
    feature_contract_sha256: str


class ModelOptionResponse(BaseModel):
    model_id: str
    label: str
    description: str
    dataset: str | None = None
    cutoff_days: int | None = Field(default=None, gt=0)
    model_version: str
    threshold: float = Field(gt=0, lt=1)
    feature_count: int = Field(gt=0)
    is_default: bool


class ModelCatalogResponse(BaseModel):
    default_model_id: str
    models: list[ModelOptionResponse]


def _require_timezone(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime values must include a UTC offset")
    return value


class StudyTask(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9._-]+$")
    title: str = Field(min_length=1, max_length=200)
    subject: str = Field(min_length=1, max_length=100)
    deadline: datetime
    estimated_minutes: int = Field(ge=15, le=10080)
    completed_minutes: int = Field(default=0, ge=0, le=10080)
    difficulty: int = Field(default=3, ge=1, le=5)
    importance: int = Field(default=3, ge=1, le=5)

    _deadline_timezone = field_validator("deadline")(_require_timezone)

    @model_validator(mode="after")
    def validate_progress(self) -> "StudyTask":
        if self.completed_minutes > self.estimated_minutes:
            raise ValueError("completed_minutes cannot exceed estimated_minutes")
        return self


class AvailabilitySlot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start: datetime
    end: datetime

    _start_timezone = field_validator("start")(_require_timezone)
    _end_timezone = field_validator("end")(_require_timezone)

    @model_validator(mode="after")
    def validate_window(self) -> "AvailabilitySlot":
        if self.end <= self.start:
            raise ValueError("availability end must be after start")
        return self


class StudyPlanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model_id: str | None = Field(default=None, pattern=MODEL_ID_PATTERN)
    features: dict[str, FeatureValue] = Field(..., min_length=1, max_length=200)
    tasks: list[StudyTask] = Field(..., min_length=1, max_length=100)
    availability: list[AvailabilitySlot] = Field(..., min_length=1, max_length=100)
    planning_time: datetime | None = None
    session_minutes: int = Field(default=50, ge=15, le=120)
    break_minutes: int = Field(default=10, ge=0, le=30)

    @field_validator("planning_time")
    @classmethod
    def validate_planning_time(cls, value: datetime | None) -> datetime | None:
        return _require_timezone(value) if value is not None else value

    @model_validator(mode="after")
    def validate_unique_tasks(self) -> "StudyPlanRequest":
        task_ids = [task.task_id for task in self.tasks]
        if len(task_ids) != len(set(task_ids)):
            raise ValueError("task_id values must be unique")
        return self


class RankedTaskResponse(BaseModel):
    task_id: str
    title: str | None = None
    subject: str | None = None
    priority_score: float = Field(ge=0, le=1)
    remaining_minutes: int = Field(ge=0)
    rationale: list[str]


class PlannedSessionResponse(BaseModel):
    task_id: str
    title: str
    subject: str
    start: datetime
    end: datetime
    study_minutes: int = Field(gt=0)
    priority_score: float = Field(ge=0, le=1)


class StudyPlanResponse(BaseModel):
    model_id: str
    risk_score: float = Field(ge=0, le=1)
    threshold: float = Field(gt=0, lt=1)
    alert: bool
    model_version: str
    ranked_tasks: list[RankedTaskResponse]
    sessions: list[PlannedSessionResponse]
    unscheduled_minutes: dict[str, int]
    recommendations: list[str]
    human_review_required: bool = True


class StudentIntake(BaseModel):
    """Small, understandable intake used by the standalone demonstration."""

    model_config = ConfigDict(extra="forbid")

    primary_goal: Literal[
        "build_consistency",
        "prepare_for_exams",
        "complete_assignments",
        "recover_missed_work",
        "balance_subjects",
    ]
    subjects: list[str] = Field(..., min_length=1, max_length=12)
    course_type: Literal[
        "theory",
        "theory_lab",
        "theory_project",
        "elective",
        "other",
    ] = "theory"
    current_term: int = Field(default=1, ge=1, le=12)
    current_credit_load: float | None = Field(default=None, ge=0, le=60)
    previous_cgpa: float | None = Field(default=None, ge=0, le=10)
    recent_score_percent: float | None = Field(default=None, ge=0, le=100)
    attendance_percent: float | None = Field(default=None, ge=0, le=100)
    submission_rate_percent: float | None = Field(default=None, ge=0, le=100)
    weekly_study_hours: float | None = Field(default=None, ge=0, le=100)
    confidence_level: int | None = Field(default=None, ge=1, le=5)
    sleep_hours: float = Field(..., ge=0, le=24)
    stress_level: int = Field(..., ge=0, le=10)
    fatigue_level: int = Field(..., ge=0, le=10)
    concentration_level: int = Field(..., ge=0, le=10)

    @field_validator("subjects")
    @classmethod
    def validate_subjects(cls, values: list[str]) -> list[str]:
        cleaned = [value.strip() for value in values]
        if any(not value or len(value) > 80 for value in cleaned):
            raise ValueError("subjects must contain non-empty names of at most 80 characters")
        if len(cleaned) != len(set(value.casefold() for value in cleaned)):
            raise ValueError("subjects must be unique")
        return cleaned


class StudentStudyPlanRequest(BaseModel):
    """Student-facing plan request; fitted features are derived by the API."""

    model_config = ConfigDict(extra="forbid")

    intake: StudentIntake
    tasks: list[StudyTask] = Field(..., min_length=1, max_length=100)
    availability: list[AvailabilitySlot] = Field(..., min_length=1, max_length=100)
    planning_time: datetime | None = None
    session_minutes: int = Field(default=50, ge=15, le=120)
    break_minutes: int = Field(default=10, ge=0, le=30)

    @field_validator("planning_time")
    @classmethod
    def validate_planning_time(cls, value: datetime | None) -> datetime | None:
        return _require_timezone(value) if value is not None else value

    @model_validator(mode="after")
    def validate_unique_tasks(self) -> "StudentStudyPlanRequest":
        task_ids = [task.task_id for task in self.tasks]
        if len(task_ids) != len(set(task_ids)):
            raise ValueError("task_id values must be unique")
        return self


class EvidenceSummary(BaseModel):
    evidence_mode: Literal["self_reported_demo"] = "self_reported_demo"
    institutional_data_connected: bool = False
    mapped_feature_count: int = Field(ge=0)
    unavailable_feature_count: int = Field(ge=0)
    coverage_percent: float = Field(ge=0, le=100)
    reliability: Literal["limited", "partial", "institutional"]
    source_labels: list[str]
    message: str


class StudentStudyPlanResponse(BaseModel):
    """Student-safe response without model columns, hashes, or registry details."""

    support_level: Literal["standard_planning", "review_recommended"]
    alert: bool
    ranked_tasks: list[RankedTaskResponse]
    sessions: list[PlannedSessionResponse]
    unscheduled_minutes: dict[str, int]
    recommendations: list[str]
    evidence: EvidenceSummary
    human_review_required: bool = True
