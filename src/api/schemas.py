"""Validated API request and response schemas."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class RiskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    features: dict[str, Any] = Field(..., min_length=1, max_length=200)


class RiskResponse(BaseModel):
    risk_score: float = Field(ge=0, le=1)
    threshold: float = Field(ge=0, le=1)
    alert: bool
    model_version: str
