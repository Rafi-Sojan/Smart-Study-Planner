"""Validated API request and response schemas."""

from __future__ import annotations

from datetime import datetime

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


class RiskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    features: dict[str, FeatureValue] = Field(..., min_length=1, max_length=200)


class RiskResponse(BaseModel):
    risk_score: float = Field(ge=0, le=1)
    threshold: float = Field(ge=0, le=1)
    alert: bool
    model_version: str
    feature_contract_sha256: str
    threshold_source: str


class ModelMetadataResponse(BaseModel):
    model_version: str
    model_source: str
    registry_name: str | None = None
    registry_version: str | None = None
    threshold: float = Field(gt=0, lt=1)
    threshold_source: str
    feature_count: int = Field(ge=0)
    feature_names: list[str]
    feature_contract_sha256: str


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
    risk_score: float = Field(ge=0, le=1)
    threshold: float = Field(gt=0, lt=1)
    alert: bool
    model_version: str
    ranked_tasks: list[RankedTaskResponse]
    sessions: list[PlannedSessionResponse]
    unscheduled_minutes: dict[str, int]
    recommendations: list[str]
    human_review_required: bool = True
