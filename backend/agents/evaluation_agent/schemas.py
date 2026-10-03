"""Schemas for Agent 6 answer evaluation."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

Verdict = Literal["strong", "adequate", "weak", "insufficient", "off_topic"]


class EvaluationResult(BaseModel):
    score: float = Field(ge=0, le=100)
    verdict: Verdict = "adequate"
    strengths: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    resume_alignment: str = ""
    jd_alignment: str = ""
    web_insights: list[str] = Field(default_factory=list)
    feedback_for_agent4: str = ""
    suggested_next_focus: str = ""
    suggest_followup: bool = True
    followup_hints: list[str] = Field(default_factory=list)
    chroma_examples: list[str] = Field(default_factory=list)
    model: str = "openai/gpt-oss-120b"
    provider: str = "meta_llama_groq"


class EvaluateAnswerRequest(BaseModel):
    question_id: str = ""
    question_text: str = Field(min_length=1, max_length=4000)
    candidate_answer: str = Field(min_length=1, max_length=8000)
    skill_tags: list[str] = Field(default_factory=list)
    use_web: bool = True


class EvaluateAnswerResponse(BaseModel):
    candidate_id: str
    evaluation: EvaluationResult
    context_used: dict[str, Any] = Field(default_factory=dict)
