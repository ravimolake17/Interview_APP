"""Schemas for Agent 7 HR recommendation reports."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

RecommendationDecision = Literal["HIRE", "CONSIDER", "REJECT", "HOLD"]
ReportStage = Literal["preliminary", "final"]


class SimilarPastCase(BaseModel):
    candidate_id: str | None = None
    decision: str | None = None
    score: float | None = None
    role: str | None = None
    quality: str | None = None
    similarity: float | None = None
    excerpt: str = ""


class HrRecommendationReport(BaseModel):
    decision: RecommendationDecision = "HOLD"
    overall_score: float = Field(ge=0, le=100, default=0)
    screening_score: float = Field(ge=0, le=100, default=0)
    interview_score: float = Field(ge=0, le=100, default=0)
    integrity_risk: float = Field(ge=0, le=100, default=0)
    interview_attempted: bool = False
    incomplete: bool = False
    left_early: bool = False
    questions_total: int = 0
    questions_answered: int = 0
    stage: ReportStage = "preliminary"
    executive_summary: str = ""
    strengths: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    rationale: str = ""
    next_steps: list[str] = Field(default_factory=list)
    integrity_notes: str = ""
    chroma_recommendation: str | None = None
    similar_past_cases: list[SimilarPastCase] = Field(default_factory=list)
    model: str = "heuristic"
    provider: str = "fallback"


class GenerateRecommendationRequest(BaseModel):
    force: bool = False


class HrRecommendationResponse(BaseModel):
    candidate_id: str
    report_id: int | None = None
    full_name: str | None = None
    job_position: str | None = None
    report: HrRecommendationReport
    created_at: datetime | None = None
    capabilities: dict[str, Any] = Field(default_factory=dict)
