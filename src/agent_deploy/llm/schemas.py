"""Pydantic models for LLM-structured output."""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class Decision(str, Enum):
    """Post-deploy analysis verdict."""

    PROCEED = "proceed"
    ROLLBACK = "rollback"
    INVESTIGATE = "investigate"


class Evidence(BaseModel):
    """A single piece of observability evidence supporting a deploy verdict."""

    signal: str
    description: str
    severity: Literal["low", "medium", "high", "critical"]
    correlated_change: str | None = Field(
        default=None,
        description="Which changelog entry this anomaly relates to",
    )


class AnalysisResult(BaseModel):
    """Structured output from the deploy-health analysis LLM call."""

    decision: Decision
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str
    evidence: list[Evidence]
    recommendations: list[str]
